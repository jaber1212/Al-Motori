# mainapp/views/auth_views.py
from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework import status as http
from rest_framework import views, permissions, status
from django.db.models import Q   # ✅ add this lin

from mainapp.models import Profile
from mainapp.serializers.authSerializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    ProfileUpdateSerializer, SendOTPSerializer, VerifyOTPSerializer
)
from mainapp.utils import api_ok, api_err
from  mainapp.models import Notification
# Your WhatsApp sender (already implemented by you)
from mainapp.OTPSender.whatsappApi import send_whatsapp_template
from  .coreViews import  _auth_user_from_request
from mainapp.serializers.authSerializers import NotificationSerializer,ForgetPasswordSendOTPSerializer,ForgetPasswordVerifySerializer  # we’ll create this below

# ---------------------------------
# Helpers
# ---------------------------------
def normalize_phone_e164(raw_phone: str, default_region: str = "JO") -> str:
    """
    Normalize to E.164 (+XXXXXXXX) for WhatsApp. Default region JO (Jordan).
    Requires 'phonenumbers' package.
    """
    import phonenumbers
    try:
        num = phonenumbers.parse(str(raw_phone), default_region)
        if not phonenumbers.is_possible_number(num) or not phonenumbers.is_valid_number(num):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except Exception as e:
        # Let caller handle the message; here we just raise
        raise ValueError(f"Invalid phone: {raw_phone}")

def send_whatsapp_otp(to_e164: str, code: str, template_name: str = "ja_otp"):
    """
    Thin wrapper around your WhatsApp template sender.
    - Puts the OTP in the first body param.
    - Also passes it as the 1st URL button param (index '0') if template has a button.
    """
    return send_whatsapp_template(
        to_e164=to_e164,
        template_name=template_name,
        lang_code="en",
        body_params=[{"type": "text", "text": str(code)}],
        url_button_params={"0": str(code)},
    )

# ---------------------------------
# Logout
# ---------------------------------
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


# ---------------------------------
# Login (blocked until phone is verified)
# ---------------------------------
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

        # Enforce phone verification before issuing token
        prof = getattr(user, "profile", None)
        if not prof or not prof.is_verified:
            # Optional: silently re-send OTP here if you want
            try:
                # Only attempt resend if profile exists & phone is parseable
                if prof and prof.phone:
                    to_e164 = normalize_phone_e164(prof.phone)
                    if prof.op_code:
                        send_whatsapp_otp(to_e164, prof.op_code, template_name="ja_otp")
            except Exception:
                # don't block the message on resend failure
                pass
            return api_err("Phone not verified. Please verify the OTP sent to your WhatsApp.", code="NOT_VERIFIED")

        token, _ = Token.objects.get_or_create(user=user)

        if player_id and prof:
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


# ---------------------------------
# Me Profile
# ---------------------------------
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


# ---------------------------------
# Send OTP (regenerate + WhatsApp)
# ---------------------------------
class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Body: { "phone": "<raw>" }
        - Validates the phone exists
        - Regenerates OTP
        - Sends via WhatsApp
        """
        s = SendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        # Save() generates a new OTP and stores it in profile.op_code
        result = s.save()

        # Serializer stored the profile on self.profile in validate(); reuse it
        profile = s.profile
        try:
            to_e164 = normalize_phone_e164(profile.phone)
        except ValueError as e:
            return api_err(str(e), code="BAD_PHONE")

        # Send OTP via WhatsApp
        try:
            send_whatsapp_otp(to_e164, profile.op_code, template_name="ja_otp")
        except Exception as e:
            # You can map provider exceptions to a better message/code if you like
            return api_err("Failed to send OTP via WhatsApp. Try again later.", code="OTP_SEND_FAILED")

        # Keep the payload clean; no OTP in response
        return api_ok("OTP sent.", data=result, code="OTP_SENT")


# ---------------------------------
# Verify OTP
# ---------------------------------
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Body: { "phone": "...", "code": "123456" }
        - Validates phone & code
        - Marks profile.is_verified = True
        """
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return api_ok("Verified.", data=result, code="OTP_VERIFIED")


# ---------------------------------
# Register (create user + profile, then WhatsApp OTP)
# ---------------------------------
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Body: { name, phone, email, password }
        - Serializer:
            - validates duplicates
            - creates User + Profile
            - generates and stores op_code
        - Here:
            - send WhatsApp OTP using stored op_code
            - return token (optional) but still require verification for login
        """
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        with transaction.atomic():
            user = s.save()
            token, _ = Token.objects.get_or_create(user=user)
            profile = user.profile  # created in serializer
            profile_data = ProfileSerializer(profile).data

        # Send OTP via WhatsApp using profile.op_code
        try:
            to_e164 = normalize_phone_e164(profile.phone)
        except ValueError as e:
            # If phone is invalid for WhatsApp, keep the account but surface the issue
            return api_err(str(e), code="BAD_PHONE")

        try:
            send_whatsapp_otp(to_e164, profile.op_code, template_name="ja_otp")
        except Exception:
            # Don’t rollback the account creation; just report sending failure
            return api_err(
                "Registered but failed to send OTP via WhatsApp. Use /auth/send-otp to retry.",
                code="REGISTERED_OTP_SEND_FAILED"
            )

        return api_ok(
            "Registered. OTP sent via WhatsApp.",
            data={"token": token.key, "profile": profile_data},
            code="REGISTER_OK",
        )




class MyNotificationsView(APIView):
    """
    POST /api/notifications/my
    Body:
      - token: required

    Returns:
      { "status": true, "message": "Notifications fetched", "data": [...] }
    """
    permission_classes = [permissions.AllowAny]  # manual token auth

    def post(self, request):
        # 1️⃣ Authenticate via token
        user = _auth_user_from_request(request)
        if not user:
            return api_err("Authentication required")

        # 2️⃣ Fetch notifications (personal + global)
        qs = (
            Notification.objects
            .filter(Q(target="all") | Q(user=user))
            .order_by("-created_at")
        )

        # 3️⃣ Serialize and respond
        data = NotificationSerializer(qs, many=True).data
        return api_ok("Notifications fetched", data=data)
# ---------------------------------
# Forget Password - Send OTP
# ---------------------------------
class ForgetPasswordSendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = ForgetPasswordSendOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        profile = s.validated_data["profile"]

        # Normalize phone number for WhatsApp
        try:
            to_e164 = normalize_phone_e164(profile.phone)
        except Exception:
            return api_err("Invalid phone number format.", code="BAD_PHONE")

        # Send WhatsApp OTP
        try:
            send_whatsapp_otp(to_e164, profile.op_code, template_name="ja_otp")
        except Exception as e:
            return api_err(f"Failed to send OTP via WhatsApp. {str(e)}", code="OTP_SEND_FAILED")

        return api_ok("OTP sent to your WhatsApp.", data={"phone": profile.phone}, code="FORGET_OTP_SENT")


# ---------------------------------
# Forget Password - Verify and Reset
# ---------------------------------
class ForgetPasswordVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = ForgetPasswordVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = s.save()
        return api_ok("Password reset successful.", data=result, code="PASSWORD_RESET_OK")
