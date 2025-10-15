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

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "status": True,
            "message": "Registered. OTP sent.",
            "token": token.key,
            "profile": ProfileSerializer(user).data
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
                return Response({"detail": "Invalid credentials."}, status=400)

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

class MyAdsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        qs = (Ad.objects
              .filter(owner=request.user)
              .order_by("-created_at")
              .prefetch_related("values__field","media"))
        # no pagination? if you want, fine—else keep paginator
        paginator = PageNumberPagination(); paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        data = AdDetailSerializer(page, many=True).data
        return ok("Ads fetched", data=data)

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
