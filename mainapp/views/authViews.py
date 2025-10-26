# mainapp/views/auth_views.py
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework import status as http

from mainapp.models import Profile
from mainapp.serializers.authSerializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    ProfileUpdateSerializer, SendOTPSerializer, VerifyOTPSerializer
)
from mainapp.utils import api_ok, api_err

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        profile = Profile.objects.get(user=request.user)
        profile.player_id = None
        profile.save(update_fields=["player_id"])
        Token.objects.filter(user=request.user).delete()
        return api_ok("Logout successful. Player ID cleared and token removed.", code="LOGOUT_OK")
    except Profile.DoesNotExist:
        return api_err("Profile not found.", code="PROFILE_NOT_FOUND")

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        phone     = s.validated_data["phone"]
        password  = s.validated_data["password"]
        player_id = s.validated_data.get("player_id")

        user = authenticate(username=phone, password=password)
        if not user:
            # manual fallback
            try:
                u = User.objects.get(username=phone)
                if not u.check_password(password):
                    return api_err("Invalid credentials.", code="AUTH_FAILED")
                user = u
            except User.DoesNotExist:
                return api_err("Invalid credentials.", code="AUTH_FAILED")

        token, _ = Token.objects.get_or_create(user=user)

        if player_id:
            prof = getattr(user, "profile", None)
            if prof:
                prof.player_id = player_id
                prof.save(update_fields=["player_id"])

        return api_ok(
            "Logged in.",
            data={
                "token": token.key,
                "profile": ProfileSerializer(user.profile).data
            },
            code="LOGIN_OK"
        )

class MeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token, _ = Token.objects.get_or_create(user=request.user)
        return api_ok(
            "Logged in.",
            data={
                "token": token.key,
                "profile": ProfileSerializer(request.user.profile).data
            },
            code="ME_OK"
        )

    def patch(self, request):
        s = ProfileUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.update(request.user, s.validated_data)
        return api_ok(
            "Profile updated.",
            data={"profile": ProfileSerializer(user.profile).data},
            code="PROFILE_UPDATED"
        )

class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = SendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return api_ok("OTP sent.", data=result, code="OTP_SENT")

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return api_ok("Verified.", data=result, code="OTP_VERIFIED")

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        with transaction.atomic():
            user = s.save()
            token, _ = Token.objects.get_or_create(user=user)
            profile_data = ProfileSerializer(user.profile).data

        return api_ok(
            "Registered. OTP sent.",
            data={"token": token.key, "profile": profile_data},
            code="REGISTER_OK",
        )
