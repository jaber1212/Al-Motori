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
from .serializers import success_responseArray
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    ProfileUpdateSerializer, SendOTPSerializer, VerifyOTPSerializer
)

from rest_framework.authtoken.models import Token



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

from rest_framework.decorators import (
    api_view, permission_classes, parser_classes,
    authentication_classes
)

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from .models import Profile
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        # Clear player_id
        profile = Profile.objects.get(user=request.user)
        profile.player_id = None
        profile.save()

        # Optionally delete token
        Token.objects.filter(user=request.user).delete()

        return success_response("Logout successful. Player ID cleared and token removed.")
    except Profile.DoesNotExist:
        return error_response("Profile not found.")
    


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
        return success_responseArray("Ads fetched", data=serializer.data)

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



from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import AdCategory, FieldDefinition, Ad, AdFieldValue, AdMedia
from .serializers import (
    PublicFieldSerializer,  # from your serializers.py (the schema field serializer)
    AdCreateSerializer, AdUpdateSerializer, AdDetailSerializer
)

# ---------- small helpers ----------

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

def _localize(item, locale, en_key, ar_key):
    if locale == "ar":
        return (item.get(ar_key) or item.get(en_key) or "").strip()
    return (item.get(en_key) or item.get(ar_key) or "").strip()

def _parse_values_field(payload):
    """
    'values' may arrive as JSON string (multipart) or dict (JSON).
    Return dict or fail.
    """
    v = payload.get("values")
    if isinstance(v, dict) or v is None:
        return v or {}
    if isinstance(v, str):
        import json
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

# You already have _save_upload(file_obj, subdir) in your file. Reuse it.

def _as_bool(v):
    """
    Accepts: True/False, "true"/"false", "1"/"0", "yes"/"no", "on"/"off", 1/0.
    Returns a real bool or None if empty/missing.
    """
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
    # fallback: anything non-empty is True
    return True

class AdFormView(APIView):
    """
    GET  /api/ads/form?category=<key>&locale=<en|ar>&token=[opt]&ad_id=[opt]
      - If token + ad_id are present and user owns the ad -> returns prefilled 'value' per field (edit mode)
      - Else returns blank schema (create mode)

    POST /api/ads/form    (JSON or multipart)
      - Body must include token (header or body/query)
      - If body has ad_id -> EDIT that ad
      - Else -> CREATE new ad
      - Core fields: title, price, city
      - Dynamic fields: values = { "<fieldKey>": <value>, ... }
      - Optional media: images[] and video (multipart) OR images:[urls], video:"url" in JSON
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # ---------- GET: schema (with optional prefill) ----------
    def get(self, request):
        category_key = request.query_params.get("category")
        if not category_key:
            return Response({"status": False, "message": "category is required"}, status=400)

        locale = (request.query_params.get("locale") or "en").lower()
        if locale not in ("en", "ar"):
            locale = "en"

        ad_id = request.query_params.get("ad_id")
        user = _auth_user_from_request(request)

        cat = get_object_or_404(AdCategory, key=category_key)

        # Dynamic fields
        fqs = (FieldDefinition.objects
               .filter(category=cat)
               .select_related("type")
               .order_by("order_index", "key"))
        dynamic = PublicFieldSerializer(fqs, many=True).data
        for item in dynamic:
            item["label"] = _localize(item, locale, "label_en", "label_ar")
            item["placeholder"] = _localize(item, locale, "placeholder_en", "placeholder_ar")

        # Core fields definition
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
               {
        "key": "isPublick",
        "type": "boolean",  # client can render a switch
        "label": "عرض الإعلان للعامة" if locale == "ar" else "Public (publish)",
        "required": False,
        "placeholder": "",
    }
        ]

        mode = "create"
        ad_hint = {}
        submit = {"method": "POST", "url": "/api/ads/form"}

        # If edit requested
        if ad_id:
            if not user:
                return Response({"status": False, "message": "Authentication required for edit"}, status=401)

            ad = get_object_or_404(
                Ad.objects.prefetch_related(
                    Prefetch("values", queryset=AdFieldValue.objects.select_related("field"))
                ),
                id=ad_id, owner=user, category=cat
            )

            # Prefill core
            core_map = {"title": ad.title, "price": ad.price, "city": ad.city, "isPublick": (ad.status == "published")}
            for cf in core_fields:
                cf["value"] = core_map.get(cf["key"])

            # Prefill dynamic (prefer matching locale if provided in AdFieldValue.locale, else any)
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
            "status": True,
            "message": "Form schema",
            "data": {
                "mode": mode,
                "category": {"key": cat.key, "name_en": cat.name_en, "name_ar": cat.name_ar},
                "locale": locale,
                "core_fields": core_fields,
                "dynamic_fields": dynamic,
                "submit": submit,
                "ad": ad_hint  # present only for edit
            }
        }
        return Response(payload, status=200)

    # ---------- POST: create or edit (same body shape) ----------
    def post(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return Response({"status": False, "message": "Authentication required"}, status=401)

        data = request.data.copy()
        ad_id = data.get("ad_id")

        # Extract files (multipart) before building serializer payload
        image_files, video_file = _extract_files(request)

        # Build payload: keep known fields; 'values' may need parsing
        payload = {}
        for k in ("category", "title", "price", "city", "values", "images", "video"):
            if k in data:
                payload[k] = data[k]

        # Parse values (if string)
        try:
            payload["values"] = _parse_values_field(payload)
        except ValueError as e:
            return Response({"status": False, "message": str(e)}, status=400)

        # If files present, don't pass images/video URLs to serializers
        if image_files or video_file:
            payload.pop("images", None)
            payload.pop("video", None)

        # ------------- create or edit -------------
        if not ad_id:
            if not payload.get("category"):
                return Response({"status": False, "message": "category is required"}, status=400)
            try:
                s = AdCreateSerializer(data=payload, context={"request": request})
                s.is_valid(raise_exception=True)
            except ValidationError as e:
                return Response({"status": False, "message": first_error_message(e.detail)}, status=400)

            ad = s.save()
            if not ad.owner_id:
                ad.owner = user
                ad.save(update_fields=["owner"])
        else:
            ad = get_object_or_404(Ad, id=ad_id, owner=user)
            try:
                s = AdUpdateSerializer(data=payload, context={"ad": ad})
                s.is_valid(raise_exception=True)
                s.update(ad, s.validated_data)
            except ValidationError as e:
                return Response({"status": False, "message": first_error_message(e.detail)}, status=400)

        # ------------- media handling -------------
        MAX_IMAGES = 12

        # Files (multipart)
        if image_files:
            if len(image_files) > MAX_IMAGES:
                return Response({"status": False, "message": f"Max {MAX_IMAGES} images allowed"}, status=400)
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, f in enumerate(image_files[:MAX_IMAGES]):
                url = _save_upload(f, subdir="ads/images")
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=idx)

        if video_file:
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            url = _save_upload(video_file, subdir="ads/videos")
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=url, order_index=0)

        # JSON URLs (when not uploading files)
        if not image_files and isinstance(data.get("images"), list):
            images_urls = data.get("images") or []
            if len(images_urls) > MAX_IMAGES:
                return Response({"status": False, "message": f"Max {MAX_IMAGES} images allowed"}, status=400)
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            for idx, u in enumerate(images_urls):
                AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=idx)

        if not video_file and isinstance(data.get("video"), str):
            v = data.get("video")
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            if v:
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)

        # ------------- NEW: publish/draft via isPublick -------------
        is_publick = _as_bool(data.get("isPublick"))
        if is_publick is True:
            # publish
            if ad.status != "published":
                ad.status = "published"
                ad.published_at = timezone.now()
                ad.save(update_fields=["status", "published_at"])
        elif is_publick is False:
            # draft
            if ad.status != "draft" or ad.published_at is not None:
                ad.status = "draft"
                ad.published_at = None
                ad.save(update_fields=["status", "published_at"])
        # If None -> user did not touch it; keep current status

        return Response({
            "status": True,
            "message": "Saved",
            "data": {
                **AdDetailSerializer(ad).data,
                "isPublick": (ad.status == "published")
            }
        }, status=200)

def first_error_message(detail):
    if isinstance(detail, dict):
        return first_error_message(next(iter(detail.values())))
    if isinstance(detail, (list, tuple)):
        return first_error_message(detail[0]) if detail else "Invalid input."
    if isinstance(detail, ErrorDetail):
        return str(detail)
    return str(detail)

# views_ads_media.py
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError

# from .models import Ad, AdMedia  # <- make sure these exist
# from .serializers import AdDetailSerializer  # optional for GET return
# from .utils import _auth_user_from_request, _save_upload  # your helpers

class AdMediaView(APIView):
    """
    Media management for an Ad.

    GET    /api/ads/media?ad_id=123
      -> list current media (images + optional single video)

    POST   /api/ads/media  (multipart OR JSON)
      Body:
        ad_id: int (required)
        images[]: files (optional, multiple)      [multipart]
        video: file (optional)                     [multipart]
        images: ["url1","url2",...]               [JSON]
        video: "url"                              [JSON]
        replace_video: true|false (optional)      [JSON/form] default False
      -> appends media respecting limits (max 10 images, max 1 video). If video exists and replace_video not true, rejects.

    DELETE /api/ads/media
      Query/body:
        ad_id: int (required)
        media_id: int (optional)  -> delete specific media
        kind: image|video         -> delete all of that kind for the ad (if media_id not provided)

    PUT    /api/ads/media/reorder
      Body (JSON):
        ad_id: int (required)
        order: [media_id1, media_id2, ...]  -> applies order for images only
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    MAX_IMAGES = 10
    MAX_VIDEO = 1
    IMAGE_SUBDIR = "ads/images"
    VIDEO_SUBDIR = "ads/videos"

    # ---------- GET: list media ----------
    def get(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return Response({"status": False, "message": "Authentication required"}, status=401)

        ad_id = request.query_params.get("ad_id")
        if not ad_id:
            return Response({"status": False, "message": "ad_id is required"}, status=400)

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return Response({"status": True, "message": "Media list", "data": data}, status=200)

    # ---------- POST: upload / append media ----------
    @transaction.atomic
    def post(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return Response({"status": False, "message": "Authentication required"}, status=401)

        data = request.data
        ad_id = data.get("ad_id")
        if not ad_id:
            return Response({"status": False, "message": "ad_id is required"}, status=400)

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        # extract uploaded files if any (multipart)
        image_files, video_file = self._extract_files(request)
        # or JSON urls
        images_urls = data.get("images") if isinstance(data.get("images"), list) else []
        video_url = data.get("video") if isinstance(data.get("video"), str) else None

        replace_video = str(data.get("replace_video", "false")).lower() in ("1", "true", "yes")

        # current counts
        current_images = ad.media.filter(kind=AdMedia.IMAGE).count()
        current_videos = ad.media.filter(kind=AdMedia.VIDEO).count()

        # ---- enforce image limit
        new_image_count = len(image_files) if image_files else len(images_urls)
        if new_image_count:
            can_add = self.MAX_IMAGES - current_images
            if can_add <= 0:
                return Response({"status": False, "message": f"Max {self.MAX_IMAGES} images already reached"}, status=400)
            if new_image_count > can_add:
                return Response({"status": False, "message": f"Can only add {can_add} more image(s). Max is {self.MAX_IMAGES}."}, status=400)

        # ---- enforce video limit
        wants_video = bool(video_file or video_url)
        if wants_video:
            if current_videos >= self.MAX_VIDEO and not replace_video:
                return Response({"status": False, "message": "A video already exists. Set replace_video=true to overwrite."}, status=400)

        # save images
        if new_image_count:
            start_index = ad.media.filter(kind=AdMedia.IMAGE).aggregate(c=Count("id"))["c"] or 0
            if image_files:  # multipart files
                for idx, f in enumerate(image_files):
                    url = _save_upload(f, subdir=self.IMAGE_SUBDIR)
                    AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=url, order_index=start_index + idx)
            else:  # urls
                for idx, u in enumerate(images_urls):
                    AdMedia.objects.create(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=start_index + idx)

        # save/replace video
        if wants_video:
            if replace_video:
                ad.media.filter(kind=AdMedia.VIDEO).delete()
            elif current_videos >= self.MAX_VIDEO:
                # defensive (should already be caught)
                return Response({"status": False, "message": "Video already exists"}, status=400)

            if video_file:
                v_url = _save_upload(video_file, subdir=self.VIDEO_SUBDIR)
            else:
                v_url = video_url
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v_url, order_index=0)

        # return fresh list
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data_out = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return Response({"status": True, "message": "Media updated", "data": data_out}, status=200)

    # ---------- DELETE: remove media ----------
    @transaction.atomic
    def delete(self, request):
        user = _auth_user_from_request(request)
        if not user:
            return Response({"status": False, "message": "Authentication required"}, status=401)

        ad_id = request.query_params.get("ad_id") or request.data.get("ad_id")
        if not ad_id:
            return Response({"status": False, "message": "ad_id is required"}, status=400)

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        media_id = request.query_params.get("media_id") or request.data.get("media_id")
        kind = (request.query_params.get("kind") or request.data.get("kind") or "").lower()

        if media_id:
            deleted, _ = ad.media.filter(id=media_id).delete()
            if not deleted:
                return Response({"status": False, "message": "media_id not found"}, status=404)
        else:
            if kind not in ("image", "video"):
                return Response({"status": False, "message": "Provide media_id or kind=image|video"}, status=400)
            ad.media.filter(kind=AdMedia.IMAGE if kind == "image" else AdMedia.VIDEO).delete()

        # re-pack list
        media_qs = ad.media.order_by("kind", "order_index", "id").values("id", "kind", "url", "order_index")
        data_out = {
            "ad_id": ad.id,
            "images": [m for m in media_qs if m["kind"] == AdMedia.IMAGE],
            "video": next((m for m in media_qs if m["kind"] == AdMedia.VIDEO), None)
        }
        return Response({"status": True, "message": "Media deleted", "data": data_out}, status=200)

    # ---------- PUT: reorder images ----------
    @transaction.atomic
    def put(self, request):
        # use a separate path /api/ads/media/reorder if you prefer; router here for simplicity
        user = _auth_user_from_request(request)
        if not user:
            return Response({"status": False, "message": "Authentication required"}, status=401)

        data = request.data
        ad_id = data.get("ad_id")
        order = data.get("order")
        if not ad_id:
            return Response({"status": False, "message": "ad_id is required"}, status=400)
        if not isinstance(order, list) or not order:
            return Response({"status": False, "message": "order must be a non-empty list of media_ids"}, status=400)

        ad = get_object_or_404(Ad.objects.filter(owner=user), id=ad_id)

        images_qs = ad.media.filter(kind=AdMedia.IMAGE)
        valid_ids = set(images_qs.values_list("id", flat=True))
        if not set(order).issubset(valid_ids):
            return Response({"status": False, "message": "order contains invalid media_ids"}, status=400)

        # apply order_index = index in list
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
        return Response({"status": True, "message": "Images reordered", "data": data_out}, status=200)

    # ---------- helpers ----------
    def _extract_files(self, request):
        """Return (image_files, video_file) from multipart."""
        image_files = []
        video_file = None
        if hasattr(request, "FILES"):
            # images[] or images
            if "images" in request.FILES:
                # could be list or single
                files = request.FILES.getlist("images") or [request.FILES["images"]]
                image_files.extend(files)
            elif "images[]" in request.FILES:
                image_files.extend(request.FILES.getlist("images[]"))

            # video
            video_file = request.FILES.get("video")

        return (image_files, video_file)


# views.py
from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch
from .models import Ad, AdMedia, AdFieldValue, FieldDefinition

def _lang(request):
    """Decide language from ?lang=ar|en, header, or default."""
    lang = (request.GET.get("lang") or request.headers.get("Accept-Language") or "en").lower()
    return "ar" if lang.startswith("ar") else "en"

def _label(fd: FieldDefinition, lang: str):
    return (fd.label_ar or fd.label_en) if lang == "ar" else (fd.label_en or fd.label_ar or fd.key)

def _placeholder(fd: FieldDefinition, lang: str):
    return (fd.placeholder_ar or fd.placeholder_en) if lang == "ar" else (fd.placeholder_en or fd.placeholder_ar or "")

def _format_value(fd: FieldDefinition, value):
    """
    Convert JSON 'value' to a nice string for display. You can enhance per type.
    """
    if value is None:
        return ""
    t = fd.type.key if fd.type else "text"
    if t in ("multiselect",):
        if isinstance(value, list):
            return ", ".join([str(v) for v in value])
    return str(value)

# views.py
def ad_public_page_by_code(request, code: str):
    """
    Public ad page by code (only 'published' ads are shown).
    Template: templates/ads/ad_detail.html
    """
    lang = _lang(request)

    ad = get_object_or_404(
        Ad.objects
          .filter(status="published")
          .select_related("category")
          .prefetch_related(
              Prefetch("values", queryset=AdFieldValue.objects.select_related("field", "field__type")),
              Prefetch("media",  queryset=AdMedia.objects.order_by("kind", "order_index", "id")),
          ),
        code=code
    )

    # Core fields (feel free to change labels)
    core = [
        {"key": "title", "label": "العنوان" if lang == "ar" else "Title", "value": ad.title or ""},
        {"key": "price", "label": "السعر" if lang == "ar" else "Price", "value": (f"{ad.price:.2f}" if ad.price is not None else "")},
        {"key": "city",  "label": "المدينة" if lang == "ar" else "City",  "value": ad.city or ""},
        {"key": "code",  "label": "رمز الإعلان" if lang == "ar" else "Ad Code", "value": ad.code},
        {"key": "date",  "label": "تاريخ النشر" if lang == "ar" else "Published", "value": ad.published_at.strftime("%Y-%m-%d %H:%M") if ad.published_at else ""},
    ]

    # Dynamic fields (only visible_public)
    # Prefer same-locale AdFieldValue if you store 'locale'; else fallback to any
    # Build best map per field key
    best_values = {}
    for v in ad.values.all():
        k = v.field.key
        if v.field.visible_public is False:
            continue
        # prefer same-locale, else keep first seen
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

    # Media
    images = [m.url for m in ad.media.all() if m.kind == AdMedia.IMAGE]
    video  = next((m.url for m in ad.media.all() if m.kind == AdMedia.VIDEO), None)

    context = {
        "lang": lang,
        "ad": ad,
        "category": {
            "key": ad.category.key,
            "name": ad.category.name_ar if lang == "ar" else ad.category.name_en,
        },
        "core": core,
        "dynamic": dynamic,
        "images": images,
        "video": video,
        # Simple SEO/OpenGraph (tweak as you like)
        "meta": {
            "title": ad.title or (ad.category.name_ar if lang == "ar" else ad.category.name_en),
            "description": f"{ad.city or ''} • {ad.price or ''}",
            "image": images[0] if images else None,
            "url": request.build_absolute_uri(),
        }
    }
    return render(request, "ads/ad_detail.html", context)


def ad_public_page_by_id(request, ad_id: int):
    """
    Optional: render by ID but still only 'published' ads.
    """
    ad = get_object_or_404(Ad, id=ad_id, status="published")
    return ad_public_page_by_code(request, ad.code)  # reuse same renderer





from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import Ad
from .models import QRCode, QRScanLog
from .serializers import ClaimQRSerializer, ActivateQRSerializer

PUBLIC_BASE = "https://motori.a.alce-qa.com"  # edit to your domain

def _client_ip(request):
    # simple best-effort; adjust if behind proxy (use X-Forwarded-For if trusted)
    return request.META.get("REMOTE_ADDR")

class ClaimQRView(views.APIView):
    """
    Auth user binds an unused QR to his draft ad (does NOT publish yet).
    POST { ad_id, code }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s = ClaimQRSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ad = get_object_or_404(Ad, id=s.validated_data["ad_id"], owner=request.user)
        qr = get_object_or_404(QRCode, code=s.validated_data["code"])

        if qr.ad and qr.ad_id != ad.id:
            return Response({"status": False, "message": "QR already assigned to another ad."}, status=400)

        qr.ad = ad
        qr.is_assigned = True
        qr.save(update_fields=["ad", "is_assigned"])

        return Response({"status": True, "message": "QR linked to ad. Activate by scanning from the app."})


class ActivateQRView(views.APIView):
    """
    First app scan: bind if needed + activate + publish ad.
    POST { ad_id, code }
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        s = ActivateQRSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        ad = get_object_or_404(Ad, id=s.validated_data["ad_id"], owner=request.user)
        qr = get_object_or_404(QRCode, code=s.validated_data["code"])

        # If already used by another ad → reject
        if qr.ad and qr.ad_id != ad.id:
            return Response({"status": False, "message": "QR already assigned to another ad."}, status=400)

        # Bind if not bound
        if not qr.ad_id:
            qr.ad = ad
            qr.is_assigned = True

        # Activate once
        if not qr.is_activated:
            qr.is_activated = True
            if ad.status != "published":
                ad.status = "published"
                ad.published_at = timezone.now()
                ad.save(update_fields=["status", "published_at"])

        qr.save(update_fields=["ad", "is_assigned", "is_activated"])

        # Log + counters
        QRScanLog.objects.create(
            qr=qr, ad=ad,
            ip=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            referrer=request.META.get("HTTP_REFERER")
        )
        qr.mark_scanned()

        public_url = f"{PUBLIC_BASE}/ads/{ad.code}"
        return Response({"status": True, "message": "Ad published via QR.", "public_url": public_url}, status=200)



from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from .models import QRCode, QRScanLog

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
