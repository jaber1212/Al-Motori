# mainapp/views/coreViews.py
from __future__ import annotations

import os, uuid, json
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.db.models import Prefetch, Count, Q

from rest_framework import permissions, status as http, views
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.response import Response

from rest_framework.authtoken.models import Token
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from mainapp.models import QRCode, QRScanLog
from mainapp.models import (
    Ad, AdCategory, FieldDefinition, AdFieldValue, AdMedia,
    QRCode, QRScanLog
)
from mainapp.serializers.coreSerializers import (
    CategorySchemaSerializer,
    AdCreateSerializer, AdUpdateSerializer,
    AdDetailSerializer, PublicAdSerializer,
    PublicFieldSerializer, ClaimQRSerializer, ActivateQRSerializer
)
from mainapp.utils import api_ok, api_err

# ----------------------------
# Success helpers (object vs array)
# ----------------------------
def ok_obj(message="OK", data=None, code="OK", http_status=http.HTTP_200_OK):
    """Force object payload ({} when None)."""
    if data is None:
        data = {}
    return api_ok(message, data=data, code=code, http_status=http_status)

def ok_list(message="OK", data=None, code="OK", http_status=http.HTTP_200_OK):
    """Force array payload ([] when None)."""
    if data is None:
        data = []
    return api_ok(message, data=data, code=code, http_status=http_status)


# ----------------------------
# File upload utility
# ----------------------------
def _save_upload(file_obj, subdir="ads"):
    name, ext = os.path.splitext(file_obj.name)
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    rel_path = os.path.join(subdir, safe_name)
    default_storage.save(rel_path, ContentFile(file_obj.read()))
    return default_storage.url(rel_path)


# ----------------------------
# Token extraction (when not using DRF auth header)
# ----------------------------
def _auth_user_from_request(request):
    """
    Try Authorization header first: 'Token <key>'.
    Fallback to ?token= or body['token'].
    """
    auth = request.headers.get("Authorization") or ""
    token_key = None
    if auth.lower().startswith("token "):
        token_key = auth.split(" ", 1)[1].strip()
    if not token_key:
        token_key = request.query_params.get("token") or request.data.get("token")
    if not token_key:
        return None
    try:
        return Token.objects.get(key=token_key).user
    except Token.DoesNotExist:
        return None


# ----------------------------
# Inputs parsing helpers
# ----------------------------
def _parse_values_field(payload):
    """Accept dict or JSON string; return dict."""
    v = payload.get("values")
    if isinstance(v, dict) or v is None:
        return v or {}
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in 'values'")
    raise ValueError("'values' must be a JSON object")


def _extract_files(request):
    """
    Support both images[]/images and video in multipart.
    Return (image_files:list, video_file|None)
    """
    if not hasattr(request, "FILES"):
        return [], None
    images = (
        request.FILES.getlist("images")
        or request.FILES.getlist("images[]")
        or ([request.FILES.get("images")] if request.FILES.get("images") else [])
    )
    video = request.FILES.get("video")
    return images, video


def _as_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    return True


# ===========================================================
# VIEWS
# ===========================================================

class CategorySchemaView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, category_key):
        cat = get_object_or_404(AdCategory, key=category_key)
        return ok_obj("Category schema", data=CategorySchemaSerializer(cat).data, code="CATEGORY_SCHEMA_OK")


class CreateAdView(APIView):
    """
    POST /api/ads/create
    - multipart/form-data OR application/json
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        data = request.data.copy()

        # Incoming files (multipart)
        image_files, video_file = _extract_files(request)

        # Build payload for serializer (remove file fields if we have uploads)
        payload = {}
        for k in ("category", "title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        # Parse values
        if "values" in payload:
            try:
                payload["values"] = _parse_values_field(payload)
            except ValueError as e:
                return api_err(str(e), code="BAD_VALUES")

        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        # Validate & create core + dynamic + (URL media)
        s = AdCreateSerializer(data=payload, context={"request": request})
        s.is_valid(raise_exception=True)
        ad = s.save()

        # Persist uploaded media (files path)
        MAX_IMAGES = 12
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return api_err(f"Max {MAX_IMAGES} images allowed", code="MAX_IMAGES")
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)

        return ok_obj("Ad created", data=AdDetailSerializer(ad).data, code="AD_CREATE_OK", http_status=http.HTTP_201_CREATED)


class UpdateAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ad_id = request.data.get("ad_id")
        if not ad_id:
            return api_err("'ad_id' is required", code="AD_ID_REQUIRED")

        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        data = request.data.copy()

        image_files, video_file = _extract_files(request)

        payload = {}
        for k in ("title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        if "values" in payload:
            try:
                payload["values"] = _parse_values_field(payload)
            except ValueError as e:
                return api_err(str(e), code="BAD_VALUES_JSON")

        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        s = AdUpdateSerializer(data=payload)
        s.is_valid(raise_exception=True)
        s.update(ad, s.validated_data)

        # Media mutations
        MAX_IMAGES = 12
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return api_err(f"Max {MAX_IMAGES} images allowed", code="MAX_IMAGES")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)
        elif "images" in payload:
            images_urls = payload.get("images") or []
            if not isinstance(images_urls, list):
                return api_err("'images' must be an array of URLs", code="IMAGES_NOT_LIST")
            if len(images_urls) > MAX_IMAGES:
                return api_err(f"Max {MAX_IMAGES} images allowed", code="MAX_IMAGES")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, u in enumerate(images_urls):
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)
        elif "video" in payload:
            v = payload.get("video")
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            if v:
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)

        return ok_obj("Ad updated successfully", code="AD_UPDATE_OK")


class MyAdsListView(APIView):
    """
    Token in body: { "token": "<key>" }
    (kept for backward-compat; you can also rely on auth header elsewhere)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token_key = request.data.get("token")
        if not token_key:
            return api_err("Token is required", code="TOKEN_REQUIRED")

        try:
            token = Token.objects.get(key=token_key)
        except Token.DoesNotExist:
            return api_err("Invalid or expired token", code="TOKEN_INVALID")

        ads = (
            Ad.objects
              .filter(owner=token.user)
              .order_by("-created_at")
              .prefetch_related("values__field", "media")
        )
        return ok_list("Ads fetched", data=AdDetailSerializer(ads, many=True).data, code="MY_ADS_OK")


class PublishAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ad_id = request.data.get("ad_id")
        if not ad_id:
            return api_err("'ad_id' is required", code="AD_ID_REQUIRED")
        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        ad.status = "published"
        ad.published_at = timezone.now()
        ad.save(update_fields=["status", "published_at"])
        return ok_obj("Ad published successfully", code="AD_PUBLISH_OK")


class UnpublishAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ad_id = request.data.get("ad_id")
        if not ad_id:
            return api_err("'ad_id' is required", code="AD_ID_REQUIRED")
        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        ad.status = "draft"
        ad.published_at = None
        ad.save(update_fields=["status", "published_at"])
        return ok_obj("Ad unpublished successfully", code="AD_UNPUBLISH_OK")


class PublicAdByCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        ad = get_object_or_404(
            Ad.objects.prefetch_related("values__field", "media"),
            code=code, status="published"
        )
        return ok_obj("Ad fetched", data=PublicAdSerializer(ad).data, code="AD_PUBLIC_OK")


# ---------- Form (schema + create/edit in one endpoint) ----------

class AdFormView(APIView):
    """
    GET  /api/ads/form?category=<key>&locale=<en|ar>&token=[opt]&ad_id=[opt]
    POST /api/ads/form  (create or edit; supports json/multipart)
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        category_key = request.query_params.get("category")
        if not category_key:
            return api_err("category is required", code="CATEGORY_REQUIRED")

        locale = (request.query_params.get("locale") or "en").lower()
        if locale not in ("en", "ar"):
            locale = "en"

        ad_id = request.query_params.get("ad_id")
        user = _auth_user_from_request(request)

        cat = get_object_or_404(AdCategory, key=category_key)

        fqs = (
            FieldDefinition.objects
            .filter(category=cat)
            .select_related("type")
            .order_by("order_index", "key")
        )
        dynamic = PublicFieldSerializer(fqs, many=True).data

        def _localize(item, locale, en_key, ar_key):
            return (item.get(ar_key) or item.get(en_key) or "").strip() if locale == "ar" else (item.get(en_key) or item.get(ar_key) or "").strip()

        for item in dynamic:
            item["label"] = _localize(item, locale, "label_en", "label_ar")
            item["placeholder"] = _localize(item, locale, "placeholder_en", "placeholder_ar")

        core_fields = [
            {
                "key": "title",
                "type": "text",
                "label": "العنوان" if locale == "ar" else "Title",
                "required": False,
                "placeholder": "اكتب عنوان الإعلان" if locale == "ar" else "Write the ad title",
            },
            {
                "key": "price",
                "type": "currency",
                "label": "السعر" if locale == "ar" else "Price",
                "required": False,
                "placeholder": "دينار" if locale == "ar" else "JOD",
                "validation": {"minimum": 0},
            },
            {
                "key": "city",
                "type": "text",
                "label": "المدينة" if locale == "ar" else "City",
                "required": False,
                "placeholder": "عمّان" if locale == "ar" else "Amman",
            },
            {
                "key": "isPublick",
                "type": "boolean",
                "label": "عرض الإعلان للعامة" if locale == "ar" else "Public (publish)",
                "required": False,
                "placeholder": "",
            },
        ]

        mode = "create"
        ad_hint = {}
        submit = {"method": "POST", "url": "/api/ads/form"}

        if ad_id:
            if not user:
                return api_err("Authentication required for edit", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)
            ad = get_object_or_404(
                Ad.objects.prefetch_related(
                    Prefetch("values", queryset=AdFieldValue.objects.select_related("field"))
                ),
                id=ad_id, owner=user, category=cat
            )

            core_map = {"title": ad.title, "price": ad.price, "city": ad.city, "isPublick": (ad.status == "published")}
            for cf in core_fields:
                cf["value"] = core_map.get(cf["key"])

            best = {}
            for v in ad.values.all():
                k = v.field.key
                if v.locale == locale:
                    best[k] = v.value
                elif k not in best:
                    best[k] = v.value
            for item in dynamic:
                item["value"] = best.get(item["key"])

            mode = "edit"
            ad_hint = {"ad_id": ad.id, "code": ad.code}

        payload = {
            "mode": mode,
            "category": {"key": cat.key, "name_en": cat.name_en, "name_ar": cat.name_ar},
            "locale": locale,
            "core_fields": core_fields,
            "dynamic_fields": dynamic,
            "submit": submit,
            "ad": ad_hint,
        }
        return ok_obj("Form schema", data=payload, code="FORM_SCHEMA_OK")

    def post(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)

        data = request.data.copy()
        ad_id = data.get("ad_id")

        image_files, video_file = _extract_files(request)

        payload = {}
        for k in ("category", "title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        try:
            payload["values"] = _parse_values_field(payload)
        except ValueError as e:
            return api_err(str(e), code="BAD_VALUES")

        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        if not ad_id:
            if not payload.get("category"):
                return api_err("category is required", code="CATEGORY_REQUIRED")
            s = AdCreateSerializer(data=payload, context={"request": request})
            s.is_valid(raise_exception=True)
            ad = s.save()
            if not ad.owner_id:
                ad.owner = user
                ad.save(update_fields=["owner"])
        else:
            ad = get_object_or_404(Ad, id=ad_id, owner=user)
            s = AdUpdateSerializer(data=payload)
            s.is_valid(raise_exception=True)
            s.update(ad, s.validated_data)

        MAX_IMAGES = 12
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return api_err(f"Max {MAX_IMAGES} images allowed", code="MAX_IMAGES")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)

        if not image_files and isinstance(data.get("images"), list):
            images_urls = data.get("images") or []
            if len(images_urls) > MAX_IMAGES:
                return api_err(f"Max {MAX_IMAGES} images allowed", code="MAX_IMAGES")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, u in enumerate(images_urls):
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=idx)

        if not video_file and isinstance(data.get("video"), str):
            v = data.get("video")
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            if v:
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)

        # Optional publish toggle
        is_publick = _as_bool(data.get("isPublick"))
        if is_publick is True:
            if ad.status != "published":
                ad.status = "published"
                ad.published_at = timezone.now()
                ad.save(update_fields=["status", "published_at"])
        elif is_publick is False:
            if ad.status != "draft" or ad.published_at is not None:
                ad.status = "draft"
                ad.published_at = None
                ad.save(update_fields=["status", "published_at"])

        out = AdDetailSerializer(ad).data
        out["isPublick"] = (ad.status == "published")
        return ok_obj("Saved", data=out, code="FORM_SAVE_OK")


# ---------- Ad media management ----------

class AdMediaView(APIView):
    """
    GET    /api/ads/media?ad_id=123
    POST   /api/ads/media       (multipart OR JSON)
    DELETE /api/ads/media       (by media_id OR all by kind)
    PUT    /api/ads/media/reorder
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    MAX_IMAGES = 10
    MAX_VIDEO = 1
    IMAGE_SUBDIR = "ads/images"
    VIDEO_SUBDIR = "ads/videos"

    def get(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)

        ad_id = request.query_params.get("ad_id")
        if not ad_id:
            return api_err("ad_id is required", code="AD_ID_REQUIRED")

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return ok_obj("Media list", data=data, code="MEDIA_LIST_OK")

    @transaction.atomic
    def post(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)

        data = request.data
        ad_id = data.get("ad_id")
        if not ad_id:
            return api_err("ad_id is required", code="AD_ID_REQUIRED")

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        image_files, video_file = self._extract_files(request)
        images_urls = data.get("images") if isinstance(data.get("images"), list) else []
        video_url = data.get("video") if isinstance(data.get("video"), str) else None
        replace_video = str(data.get("replace_video", "false")).lower() in ("1", "true", "yes")

        current_images = ad.media.filter(kind=AdMedia.IMAGE).count()
        current_videos = ad.media.filter(kind=AdMedia.VIDEO).count()

        new_image_count = len(image_files) if image_files else len(images_urls)
        if new_image_count:
            can_add = self.MAX_IMAGES - current_images
            if can_add <= 0:
                return api_err(f"Max {self.MAX_IMAGES} images already reached", code="MAX_IMAGES")
            if new_image_count > can_add:
                return api_err(f"Can only add {can_add} more image(s). Max is {self.MAX_IMAGES}.", code="MAX_IMAGES")

        wants_video = bool(video_file or video_url)
        if wants_video:
            if current_videos >= self.MAX_VIDEO and not replace_video:
                return api_err("A video already exists. Set replace_video=true to overwrite.", code="VIDEO_EXISTS")

        # save images
        if new_image_count:
            start_index = ad.media.filter(kind=AdMedia.IMAGE).aggregate(c=Count("id"))["c"] or 0
            if image_files:
                for idx, f in enumerate(image_files):
                    url = _save_upload(f, subdir=self.IMAGE_SUBDIR)
                    AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=start_index + idx)
            else:
                for idx, u in enumerate(images_urls):
                    AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=start_index + idx)

        # save/replace video
        if wants_video:
            if replace_video:
                ad.media.filter(kind=AdMedia.VIDEO).delete()
            elif current_videos >= self.MAX_VIDEO:
                return api_err("Video already exists", code="VIDEO_EXISTS")
            v_url = _save_upload(video_file, subdir=self.VIDEO_SUBDIR) if video_file else video_url
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v_url, order_index=0)

        # return fresh list
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data_out = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return ok_obj("Media updated", data=data_out, code="MEDIA_UPDATE_OK")

    @transaction.atomic
    def delete(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)

        ad_id = request.query_params.get("ad_id") or request.data.get("ad_id")
        if not ad_id:
            return api_err("ad_id is required", code="AD_ID_REQUIRED")

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        media_id = request.query_params.get("media_id") or request.data.get("media_id")
        kind = (request.query_params.get("kind") or request.data.get("kind") or "").lower()

        if media_id:
            deleted, _ = ad.media.filter(id=media_id).delete()
            if not deleted:
                return api_err("media_id not found", code="MEDIA_NOT_FOUND", http_status=http.HTTP_404_NOT_FOUND)
        else:
            if kind not in ("image", "video"):
                return api_err("Provide media_id or kind=image|video", code="MEDIA_DELETE_ARGS")
            ad.media.filter(kind=AdMedia.IMAGE if kind == "image" else AdMedia.VIDEO).delete()

        # re-pack list
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data_out = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return ok_obj("Media deleted", data=data_out, code="MEDIA_DELETE_OK")

    @transaction.atomic
    def put(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required", code="AUTH_REQUIRED", http_status=http.HTTP_401_UNAUTHORIZED)

        data = request.data
        ad_id = data.get("ad_id")
        order = data.get("order")
        if not ad_id:
            return api_err("ad_id is required", code="AD_ID_REQUIRED")
        if not isinstance(order, list) or not order:
            return api_err("order must be a non-empty list of media_ids", code="BAD_ORDER")

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        images_qs = ad.media.filter(kind=AdMedia.IMAGE)
        valid_ids = set(images_qs.values_list("id", flat=True))
        if not set(order).issubset(valid_ids):
            return api_err("order contains invalid media_ids", code="ORDER_INVALID")

        id_to_idx = {mid: i for i, mid in enumerate(order)}
        for m in images_qs:
            if m.id in id_to_idx:
                m.order_index = id_to_idx[m.id]
                m.save(update_fields=["order_index"])

        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data_out = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return ok_obj("Images reordered", data=data_out, code="MEDIA_REORDER_OK")

    def _extract_files(self, request):
        return _extract_files(request)


# ---------- Public HTML pages (optional) ----------

def _lang(request):
    lang = (request.GET.get("lang") or request.headers.get("Accept-Language") or "en").lower()
    return "ar" if lang.startswith("ar") else "en"


def ad_public_page_by_code(request, code: str):
    lang = _lang(request)
    ad = get_object_or_404(
        Ad.objects
        .filter(status="published")
        .select_related("category")
        .prefetch_related(
            Prefetch("values", queryset=AdFieldValue.objects.select_related("field", "field__type")),
            Prefetch("media", queryset=AdMedia.objects.order_by("kind", "order_index", "id")),
        ),
        code=code
    )

    def _label(fd: FieldDefinition, lang: str):
        return (fd.label_ar or fd.label_en) if lang == "ar" else (fd.label_en or fd.label_ar or fd.key)

    def _placeholder(fd: FieldDefinition, lang: str):
        return (fd.placeholder_ar or fd.placeholder_en) if lang == "ar" else (fd.placeholder_en or fd.placeholder_ar or "")

    def _format_value(fd: FieldDefinition, value):
        if value is None:
            return ""
        t = fd.type.key if fd.type else "text"
        if t in ("multiselect",) and isinstance(value, list):
            return ", ".join([str(v) for v in value])
        return str(value)

    best_values = {}
    for v in ad.values.all():
        k = v.field.key
        if v.field.visible_public is False:
            continue
        if v.locale == lang or k not in best_values:
            best_values[k] = (v.field, v.value)

    dynamic = []
    for k, (fd, val) in best_values.items():
        dynamic.append({
            "key": k,
            "label": _label(fd, lang),
            "placeholder": _placeholder(fd, lang),
            "value_raw": val,
            "value": _format_value(fd, val),
            "type": fd.type.key if fd.type else "text",
            "order_index": fd.order_index,
        })
    dynamic.sort(key=lambda x: (x["order_index"], x["key"]))

    images = [m.url for m in ad.media.all() if m.kind == AdMedia.IMAGE]
    video  = next((m.url for m in ad.media.all() if m.kind == AdMedia.VIDEO), None)

    context = {
        "lang": lang,
        "ad": ad,
        "category": {
            "key": ad.category.key,
            "name": ad.category.name_ar if lang == "ar" else ad.category.name_en,
        },
        "core": [
            {"key": "title", "label": "العنوان" if lang == "ar" else "Title", "value": ad.title or ""},
            {"key": "price", "label": "السعر" if lang == "ar" else "Price",
             "value": (f"{ad.price:.2f}" if ad.price is not None else "")},
            {"key": "city",  "label": "المدينة" if lang == "ar" else "City", "value": ad.city or ""},
            {"key": "code",  "label": "رمز الإعلان" if lang == "ar" else "Ad Code", "value": ad.code},
            {"key": "date",  "label": "تاريخ النشر" if lang == "ar" else "Published",
             "value": ad.published_at.strftime("%Y-%m-%d %H:%M") if ad.published_at else ""},
        ],
        "dynamic": dynamic,
        "images": images,
        "video": video,
        "meta": {
            "title": ad.title or (ad.category.name_ar if lang == "ar" else ad.category.name_en),
            "description": f"{ad.city or ''} • {ad.price or ''}",
            "image": images[0] if images else None,
            "url": request.build_absolute_uri(),
        }
    }
    return render(request, "ads/ad_detail.html", context)


def ad_public_page_by_id(request, ad_id: int):
    ad = get_object_or_404(Ad, id=ad_id, status="published")
    return ad_public_page_by_code(request, ad.code)


# ---------- QR binding / activation ----------

PUBLIC_BASE = "https://motori.a.alce-qa.com"  # set to your domain

def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


class ClaimQRView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = ClaimQRSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        ad = get_object_or_404(Ad, id=s.validated_data["ad_id"], owner=request.user)
        qr = get_object_or_404(QRCode, code=s.validated_data["code"])

        if qr.ad and qr.ad_id != ad.id:
            return api_err("QR already assigned to another ad.", code="QR_TAKEN")

        qr.ad = ad
        qr.is_assigned = True
        qr.save(update_fields=["ad", "is_assigned"])

        return ok_obj("QR linked to ad. Activate by scanning from the app.", code="QR_LINK_OK")


class ActivateQRView(views.APIView):
    """
    First scan (owner): bind if needed + activate + publish ad.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        s = ActivateQRSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        ad = get_object_or_404(Ad, id=s.validated_data["ad_id"], owner=request.user)

        qr = QRCode.objects.select_for_update().filter(code=s.validated_data["code"]).first()
        if not qr:
            return api_err("Out source QR code.", code="QR_OUTSOURCE")

        if qr.ad_id and qr.ad_id != ad.id:
            return api_err("QR already assigned to another ad.", code="QR_TAKEN")

        if (qr.ad_id == ad.id) and qr.is_activated and (ad.status == "published"):
            public_url = f"{PUBLIC_BASE}/ads/{ad.code}"
            return ok_obj("Ad already active.", data={"public_url": public_url}, code="QR_ALREADY_ACTIVE")

        # Ensure an ad can't have multiple QRs
        existing_qr_for_ad = (
            QRCode.objects.select_for_update()
            .filter(ad_id=ad.id)
            .exclude(id=qr.id)
            .first()
        )
        if existing_qr_for_ad:
            return api_err("This ad already has a QR assigned.", code="AD_HAS_QR")

        if not qr.ad_id:
            qr.ad = ad
            qr.is_assigned = True

        if not qr.is_activated:
            qr.is_activated = True

        if ad.status != "published":
            ad.status = "published"
            ad.published_at = timezone.now()
            ad.save(update_fields=["status", "published_at"])

        qr.save(update_fields=["ad", "is_assigned", "is_activated"])

        QRScanLog.objects.create(
            qr=qr, ad=ad,
            ip=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            referrer=request.META.get("HTTP_REFERER"),
        )
        qr.mark_scanned()

        public_url = f"{PUBLIC_BASE}/ads/{ad.code}"
        return ok_obj("Ad published via QR.", data={"public_url": public_url}, code="QR_ACTIVATE_OK")

def qr_landing(request, code):
    qr = get_object_or_404(QRCode, code=code)

    # log every hit
    QRScanLog.objects.create(
        qr=qr, ad=qr.ad,
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT"),
        referrer=request.META.get("HTTP_REFERER"),
    )
    qr.mark_scanned()

    if not qr.ad_id:
        # unassigned sticker
        return HttpResponseNotFound("<h2>QR not assigned yet.</h2>")

    if not qr.is_activated:
        # linked but not activated by the owner from the app
        return HttpResponse("<h2>This ad is not activated yet.</h2>", status=403)

    # activated → redirect to the public ad page
    return HttpResponseRedirect(f"/ads/{qr.ad.code}")
