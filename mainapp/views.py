from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse

def home(request):
    return HttpResponse("Hello from Main App 🚀")
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token

from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    ProfileUpdateSerializer, SendOTPSerializer, VerifyOTPSerializer
)




import json, os, uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def _save_upload(file_obj, subdir="ads"):
    name, ext = os.path.splitext(file_obj.name)
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    rel_path = os.path.join(subdir, safe_name)
    default_storage.save(rel_path, ContentFile(file_obj.read()))
    return default_storage.url(rel_path)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import ValidationError, ErrorDetail
from rest_framework.authtoken.models import Token

def first_error_message(detail):
    """
    Recursively extract the first human-readable error message
    from DRF ValidationError.detail (dict/list/ErrorDetail/str).
    """
    if isinstance(detail, dict):
        # Take the first field's errors
        return first_error_message(next(iter(detail.values())))
    if isinstance(detail, (list, tuple)):
        # Take the first item in the list
        return first_error_message(detail[0]) if detail else "Invalid input."
    if isinstance(detail, ErrorDetail):
        return str(detail)
    # Fallback (string or unknown type)
    return str(detail)

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        try:
            s.is_valid(raise_exception=True)
        except ValidationError as e:
            return Response(
                {"status": False, "message": first_error_message(e.detail)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = s.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "status": True,
            "message": "Registered. OTP sent.",
            "token": token.key,
            # If your serializer is for Profile, pass user.profile (not user)
            "profile": ProfileSerializer(user.profile).data
        }, status=status.HTTP_201_CREATED)



class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone = s.validated_data["phone"]
        password = s.validated_data["password"]
        # username is phone
        user = authenticate(username=phone, password=password)
        if not user:
            # fallback: find by phone and check password manually
            try:
                u = User.objects.get(username=phone)
                if not u.check_password(password):
                    return Response({"detail": "Invalid credentials."}, status=400)
                user = u
            except User.DoesNotExist:
                return error_
                Response({"detail": "Invalid credentials."}, status=400)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "status": True,
            "message": "Logged in.",
            "token": token.key,
            "profile": ProfileSerializer(user).data
        })

class MeProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        token, _ = Token.objects.get_or_create(user=request.user)

        return Response({
            "status": True,
            "message": "Logged in.",
            "token": token.key,

            "profile":ProfileSerializer(request.user).data})

    def patch(self, request):
        s = ProfileUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.update(request.user, s.validated_data)
        return Response(ProfileSerializer(user).data)

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = SendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response({"status": True, **result})

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response({"status": True, **result})



# =====Ads Bahviors =======
# ===== Ads Behaviors (GET/POST only) =====
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Ad, AdCategory, AdMedia, FieldDefinition, AdFieldValue
from .serializers import (
    CategorySchemaSerializer,
    AdCreateSerializer, AdUpdateSerializer,
    AdDetailSerializer, PublicAdSerializer,
)

MAX_IMAGES = 12

class CategorySchemaView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, category_key):
        cat = get_object_or_404(AdCategory, key=category_key)
        return Response(CategorySchemaSerializer(cat).data)

# views.py
import json, os, uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

def _save_upload(file_obj, subdir="ads"):
    name, ext = os.path.splitext(file_obj.name)
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    rel_path = os.path.join(subdir, safe_name)
    default_storage.save(rel_path, ContentFile(file_obj.read()))
    return default_storage.url(rel_path)

class CreateAdView(APIView):
    """
    POST /api/ads/create
    Accepts:
      - multipart/form-data (recommended for file uploads)
          fields: category, title?, price?, city?, values (JSON string),
                  images (repeatable files), video (single file)
      - application/json (if you already have hosted URLs)
          body: { category, title?, price?, city?, values: {...},
                  images: ["https://..."], video: "https://..." }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        data = request.data.copy()

        # --- Extract files (multipart) ---
        image_files = []
        if hasattr(request, "FILES"):
            # support images (single key with multiple files) and images[]
            image_files = (
                request.FILES.getlist("images")
                or request.FILES.getlist("images[]")
                or ([request.FILES.get("images")] if request.FILES.get("images") else [])
            )
            video_file = request.FILES.get("video")
        else:
            video_file = None

        # --- Build payload for serializer (exclude file fields) ---
        payload = {}
        for k in ("category", "title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        # Parse values (multipart sends it as a string)
        if "values" in payload and isinstance(payload["values"], str):
            try:
                payload["values"] = json.loads(payload["values"])
            except json.JSONDecodeError:
                return Response({"detail": "Invalid JSON in 'values'."}, status=400)

        # IMPORTANT:
        # If uploading files, REMOVE images/video from payload so the serializer
        # doesn't try to treat them as URL strings.
        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        # Validate core + dynamic fields
        s = AdCreateSerializer(data=payload, context={"request": request})
        s.is_valid(raise_exception=True)
        ad = s.save()  # creates Ad + AdFieldValue (no media yet)

        # --- Persist media ---
        MAX_IMAGES = 12

        # Case A: files uploaded in multipart
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return Response({"detail": f"Max {MAX_IMAGES} images allowed"}, status=400)
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)

        # Case B: JSON with hosted URLs (no file uploads)
        # If client sent images/video as URLs in JSON, create media from them too.
        if not image_files and isinstance(payload.get("images"), list):
            for idx, u in enumerate(payload["images"][:MAX_IMAGES]):
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=idx)

        if not video_file and isinstance(payload.get("video"), str) and payload["video"]:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=payload["video"], order_index=0)

        return Response({"status": True, "ad": AdDetailSerializer(ad).data}, status=201)

class UpdateAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # 1) id from body
        try:
            ad_id = require_body_id(request, "ad_id")
        except ValueError as e:
            return fail(str(e))

        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        data = request.data.copy()

        # 2) gather files (if any)
        image_files = (
            request.FILES.getlist("images")
            or request.FILES.getlist("images[]")
            or ([request.FILES.get("images")] if request.FILES.get("images") else [])
        ) if hasattr(request, "FILES") else []
        video_file = request.FILES.get("video") if hasattr(request, "FILES") else None

        # 3) serializer payload (exclude files)
        payload = {}
        for k in ("title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        if "values" in payload and isinstance(payload["values"], str):
            try:
                payload["values"] = json.loads(payload["values"])
            except json.JSONDecodeError:
                return fail("Invalid JSON in 'values'")

        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        # 4) validate + save core/dynamic
        try:
            s = AdUpdateSerializer(data=payload)
            s.is_valid(raise_exception=True)
            s.update(ad, s.validated_data)
        except Exception as e:
            return fail("Validation failed", errors={"detail": str(e)})

        # 5) media mutations
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return fail(f"Max {MAX_IMAGES} images allowed")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)
        elif "images" in payload:
            images_urls = payload.get("images") or []
            if not isinstance(images_urls, list):
                return fail("'images' must be an array of URLs")
            if len(images_urls) > MAX_IMAGES:
                return fail(f"Max {MAX_IMAGES} images allowed")
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, u in enumerate(images_urls):
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)
        elif "video" in payload:
            v = payload.get("video")
            if v in ("", None):
                ad.media.filter(kind=AdMedia.VIDEO).delete()
            elif isinstance(v, str):
                ad.media.filter(kind=AdMedia.VIDEO).delete()
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)

        return ok("Ad updated successfully")
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.authtoken.models import Token
from .models import Ad
from .serializers import AdDetailSerializer
from .serializers import error_response, success_response  # your custom response helpers

class MyAdsListView(APIView):
    permission_classes = [permissions.AllowAny]  # since we authenticate manually

    def post(self, request):
        # 1️⃣ Read token from body
        token_key = request.data.get("token")

        if not token_key:
            return error_response("Token is required")

        # 2️⃣ Verify token and get user
        try:
            token = Token.objects.get(key=token_key)
            user = token.user
        except Token.DoesNotExist:
            return error_response("Invalid or expired token")

        # 3️⃣ Get all ads for this user
        ads = (
            Ad.objects
            .filter(owner=user)
            .order_by("-created_at")
            .prefetch_related("values__field", "media")
        )

        # 4️⃣ Serialize and return
        serializer = AdDetailSerializer(ads, many=True)
        return success_response("Ads fetched", data=serializer.data)

class MyAdsByTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        token_str = request.data.get("token")
        if not token_str:
            return fail("token is required")
        try:
            token = Token.objects.get(key=token_str)
        except Token.DoesNotExist:
            return fail("invalid token", status_code=http_status.HTTP_401_UNAUTHORIZED)

        user = token.user
        qs = (Ad.objects
              .filter(owner=user)
              .order_by("-created_at")
              .prefetch_related("values__field","media"))
        data = AdDetailSerializer(qs, many=True).data
        return ok("Ads fetched", data=data)
def require_body_id(request, field="ad_id"):
    ad_id = request.data.get(field)
    if not ad_id:
        raise ValueError(f"'{field}' is required in body")
    return ad_id

class PublishAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        try:
            ad_id = require_body_id(request, "ad_id")
        except ValueError as e:
            return fail(str(e))
        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        ad.status = "published"; ad.published_at = timezone.now()
        ad.save(update_fields=["status","published_at"])
        return ok("Ad published successfully")

class UnpublishAdView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        try:
            ad_id = require_body_id(request, "ad_id")
        except ValueError as e:
            return fail(str(e))
        ad = get_object_or_404(Ad, id=ad_id, owner=request.user)
        ad.status = "draft"; ad.published_at = None
        ad.save(update_fields=["status","published_at"])
        return ok("Ad unpublished successfully")

class PublicAdByCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, code):
        ad = get_object_or_404(
            Ad.objects.prefetch_related("values__field","media"),
            code=code, status="published"
        )
        return ok("Ad fetched", data=PublicAdSerializer(ad).data)

from rest_framework import status as http_status

def ok(message="OK", *, data=None, status_code=http_status.HTTP_200_OK):
    """
    Success response. For actions (create/edit/publish/unpublish) omit data.
    For lists or fetches, pass data=[...]/{...}.
    """
    payload = {"status": True, "message": message}
    if data is not None:
        payload["data"] = data
    return Response(payload, status=status_code)

def fail(message="Failed", *, errors=None, status_code=http_status.HTTP_400_BAD_REQUEST):
    """
    Failure response. May include errors (dict) for debugging the client;
    no 'data' by default to keep it clean.
    """
    payload = {"status": False, "message": message}
    if errors:
        payload["errors"] = errors
    return Response(payload, status=status_code)




from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework.authtoken.models import Token

from .models import AdCategory, FieldDefinition, Ad, AdFieldValue
from .serializers import PublicFieldSerializer

class AdFormSchemaView(APIView):
    """
    GET /api/ads/form-schema?category=<key>&locale=<en|ar>[&ad_id=..|&ad_code=..]
    - If ad_id/ad_code is provided, we prefill 'value' for core + dynamic fields.
    - Requires Authorization: Token <key> for edit mode (to ensure ownership).
    """
    permission_classes = [permissions.AllowAny]

    def _get_user_from_auth(self, request):
        # Expect 'Authorization: Token <token>'
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("token "):
            key = auth.split(" ", 1)[1].strip()
            try:
                return Token.objects.get(key=key).user
            except Token.DoesNotExist:
                return None
        return None

    def get(self, request):
        category_key = request.query_params.get("category")
        if not category_key:
            return Response({"status": False, "message": "category is required"}, status=400)

        locale = (request.query_params.get("locale") or "en").lower()
        if locale not in ("en", "ar"):
            locale = "en"

        # Optional edit target
        ad_id   = request.query_params.get("ad_id")
        ad_code = request.query_params.get("ad_code")

        cat = get_object_or_404(AdCategory, key=category_key)

        # 1) Base: dynamic field list
        fqs = (FieldDefinition.objects
               .filter(category=cat)
               .select_related("type")
               .order_by("order_index", "key"))
        dynamic = PublicFieldSerializer(fqs, many=True).data

        # Localizer
        def L(item, en_key, ar_key):
            return (item.get(ar_key) or item.get(en_key) or "").strip() if locale == "ar" \
                   else (item.get(en_key) or item.get(ar_key) or "").strip()

        for item in dynamic:
            item["label"] = L(item, "label_en", "label_ar")
            item["placeholder"] = L(item, "placeholder_en", "placeholder_ar")

        # 2) Core fields (static definition)
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
                "validation": {"minimum": 0}
            },
            {
                "key": "city",
                "type": "text",
                "label": "المدينة" if locale == "ar" else "City",
                "required": False,
                "placeholder": "عمّان" if locale == "ar" else "Amman",
            },
        ]

        mode = "create"
        submit = {"method": "POST", "url": "/api/ads/create"}
        ad_hint = {}

        # 3) If edit mode requested -> fetch ad + prefill 'value'
        if ad_id or ad_code:
            # must be authenticated owner
            user = self._get_user_from_auth(request)
            if not user:
                return Response({"status": False, "message": "Authentication required for edit"}, status=401)

            if ad_id:
                ad = get_object_or_404(
                    Ad.objects.prefetch_related(
                        Prefetch("values", queryset=AdFieldValue.objects.select_related("field"))
                    ),
                    id=ad_id, owner=user, category=cat
                )
            else:
                ad = get_object_or_404(
                    Ad.objects.prefetch_related(
                        Prefetch("values", queryset=AdFieldValue.objects.select_related("field"))
                    ),
                    code=ad_code, owner=user, category=cat
                )

            # core values
            core_map = {"title": ad.title, "price": ad.price, "city": ad.city}
            for cf in core_fields:
                cf["value"] = core_map.get(cf["key"])

            # dynamic values: pick value with matching locale if available, else latest
            # Build: key -> best value
            best = {}
            for v in ad.values.all():
                k = v.field.key
                if v.locale == locale:
                    best[k] = v.value
                elif k not in best:
                    # fallback: keep first seen; we'll still allow override by exact-locale later
                    best[k] = v.value

            for item in dynamic:
                item["value"] = best.get(item["key"])

            mode = "edit"
            submit = {"method": "POST", "url": "/api/ads/update"}
            ad_hint = {"ad_id": ad.id, "code": ad.code}

        payload = {
            "status": True,
            "message": "Form schema",
            "data": {
                "mode": mode,
                "category": {"key": cat.key, "name_en": cat.name_en, "name_ar": cat.name_ar},
                "locale": locale,
                "core_fields": core_fields,
                "dynamic_fields": dynamic,
                "submit": submit,
                "ad": ad_hint  # only in edit mode
            }
        }
        return Response(payload, status=status.HTTP_200_OK)
