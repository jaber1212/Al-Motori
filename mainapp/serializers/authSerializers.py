# mainapp/serializers/auth_serializers.py
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError
from rest_framework import serializers
from mainapp.models import Profile,Notification
from mainapp.utils import api_err  # only for views; DO NOT use inside serializer

def generate_otp():
    import random
    return f"{random.randint(100000, 999999)}"

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_phone(self, v):
        if Profile.objects.filter(phone=v).exists():
            raise serializers.ValidationError("Phone already registered.")
        return v

    def validate_email(self, v):
        if Profile.objects.filter(email=v).exists():
            raise serializers.ValidationError("Email already registered.")
        return v

    def create(self, validated):
        name  = validated["name"]
        phone = validated["phone"]
        email = validated["email"]
        pw    = validated["password"]

        try:
            with transaction.atomic():
                user = User.objects.create(
                    username=phone,
                    first_name=name,
                    email=email,
                    password=make_password(pw),
                )
                otp = generate_otp()
                Profile.objects.create(
                    user=user, name=name, phone=phone, email=email,
                    op_code=otp, is_verified=False
                )
                return user
        except IntegrityError as e:
            # Will be normalized by custom_exception_handler too,
            # but we can be explicit here:
            msg = str(e).lower()
            if "phone" in msg:
                raise serializers.ValidationError("Phone already registered.")
            if "email" in msg:
                raise serializers.ValidationError("Email already registered.")
            raise serializers.ValidationError("Account already exists with this phone/email.")


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    player_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ProfileSerializer(serializers.ModelSerializer):
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id", "name", "phone", "email",
            "is_verified", "op_code", "player_id", "updated_at",
            "user_first_name", "username",
        ]


class ProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)

    def update(self, user, validated):
        user.first_name = validated["name"]
        user.profile.name = validated["name"]
        user.save()
        user.profile.save()
        return user


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate(self, data):
        phone = data["phone"]
        try:
            self.profile = Profile.objects.get(phone=phone)
        except Profile.DoesNotExist:
            raise serializers.ValidationError("Phone not found.")
        return data

    def save(self, **kwargs):
        otp = generate_otp()
        self.profile.op_code = otp
        self.profile.save(update_fields=["op_code"])
        # integrate SMS here
        return {"sent": True}


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            self.profile = Profile.objects.get(phone=data["phone"])
        except Profile.DoesNotExist:
            raise serializers.ValidationError("Phone not found.")
        if self.profile.op_code != data["code"]:
            raise serializers.ValidationError("Invalid code.")
        return data

    def save(self, **kwargs):
        self.profile.is_verified = True
        self.profile.save(update_fields=["is_verified"])
        return {"verified": True}


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "target", "title", "message", "sent", "created_at"]



# mainapp/serializers/authSerializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from mainapp.models import Profile
from mainapp.utils import api_err
import random

class ForgetPasswordSendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate(self, attrs):
        phone = attrs.get("phone")
        try:
            profile = Profile.objects.get(phone=phone)
        except Profile.DoesNotExist:
            raise api_err("No account found with this phone number.", code="NO_ACCOUNT")
        attrs["profile"] = profile
        return attrs

    def save(self):
        profile = self.validated_data["profile"]
        # Generate a new OTP
        otp = str(random.randint(100000, 999999))
        profile.op_code = otp
        profile.save(update_fields=["op_code"])
        return {"phone": profile.phone, "op_code": otp}


class ForgetPasswordVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

    def validate(self, attrs):
        phone = attrs.get("phone")
        code = attrs.get("code")

        try:
            profile = Profile.objects.get(phone=phone)
        except Profile.DoesNotExist:
            raise api_err("No account found with this phone number.", code="NO_ACCOUNT")

        if not profile.op_code or profile.op_code != code:
            raise api_err("Invalid or expired OTP.", code="BAD_OTP")

        attrs["profile"] = profile
        return attrs

    def save(self):
        profile = self.validated_data["profile"]
        new_password = self.validated_data["new_password"]

        user = profile.user
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Reset OTP and mark verified if needed
        profile.is_verified = True
        profile.save(update_fields=["op_code", "is_verified"])

        return {"phone": profile.phone, "status": "password_reset"}
