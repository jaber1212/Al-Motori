# mainapp/serializers/auth_serializers.py
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError
from rest_framework import serializers
from mainapp.models import Profile
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
