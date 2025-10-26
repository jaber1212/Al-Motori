

from rest_framework.decorators import (
    api_view, permission_classes, parser_classes,
    authentication_classes)
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    ProfileUpdateSerializer, SendOTPSerializer, VerifyOTPSerializer
)

from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from .models import Profile
from django.db import transaction

from .utils import *


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
        player_id = s.validated_data["player_id"] # optional

        # username is phone
        user = authenticate(username=phone, password=password)
        if not user:
            # fallback: find by phone and check password manually
            try:
                u = User.objects.get(username=phone)
                if not u.check_password(password):
                     return error_response("Invalid credentials")
                user = u
            except User.DoesNotExist:
                return error_response("Invalid credentials")



        token, _ = Token.objects.get_or_create(user=user)
        if player_id:
            profile = getattr(user, "profile", None)
            if profile:
                profile.player_id = player_id
                profile.save(update_fields=["player_id"])

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

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        try:
            s.is_valid(raise_exception=True)
        except ValidationError as e:
            return error_response(e.detail)

        with transaction.atomic():
            user = s.save()
            token, _ = Token.objects.get_or_create(user=user)
            profile_data = ProfileSerializer(user.profile).data

        return Response({
            "status": True,
            "message": "Registered. OTP sent.",
            "token": token.key,
            "profile": profile_data
        }, status=status.HTTP_201_CREATED)


