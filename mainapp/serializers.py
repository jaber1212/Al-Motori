from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from .models import Profile
import random

def generate_otp():
    return f"{random.randint(100000, 999999)}"

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_phone(self, v):
        if Profile.objects.filter(phone=v).exists():
            raise serializers.ValidationError("Phone already registered.")
        return v

    def create(self, validated):
        name = validated["name"]
        phone = validated["phone"]
        password = validated["password"]

        # Use phone as username for simplicity
        user = User.objects.create(
            username=phone,
            first_name=name,
            password=make_password(password)
        )
        otp = generate_otp()
        Profile.objects.create(user=user, name=name, phone=phone, op_code=otp, is_verified=False)
        # TODO: send OTP via SMS provider here (stub)
        return user

class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

class ProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="profile.phone", read_only=True)
    is_verified = serializers.BooleanField(source="profile.is_verified", read_only=True)
    op_code = serializers.CharField(source="profile.op_code", read_only=True)  # expose if you want

    class Meta:
        model = User
        fields = ["first_name", "phone", "is_verified", "op_code"]  # first_name acts as name

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
        # TODO: integrate SMS gateway here
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




from rest_framework import serializers
from .models import (
    Ad, AdCategory, FieldType, FieldDefinition, AdFieldValue, AdMedia
)

MAX_IMAGES = 12

# ---- schema for mobile ----
class FieldTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldType
        fields = ["key","name","config"]

class FieldDefinitionSerializer(serializers.ModelSerializer):
    type = FieldTypeSerializer(read_only=True)
    class Meta:
        model = FieldDefinition
        fields = [
            "key","type","label_en","label_ar","required","order_index",
            "visible_public","choices","validation","placeholder_en","placeholder_ar"
        ]

class CategorySchemaSerializer(serializers.ModelSerializer):
    fields = FieldDefinitionSerializer(many=True, read_only=True)
    class Meta:
        model = AdCategory
        fields = ["key","name_en","name_ar","fields"]

# ---- create/update ----
class AdCreateSerializer(serializers.Serializer):
    category = serializers.SlugRelatedField(slug_field="key", queryset=AdCategory.objects.all())
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    price = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2)
    city  = serializers.CharField(max_length=100, required=False, allow_blank=True)

    images = serializers.ListField(child=serializers.URLField(), required=False, allow_empty=True)
    video  = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    values = serializers.DictField(child=serializers.JSONField(), required=False)

    def validate(self, data):
        # dynamic fields
        category = data["category"]
        defs = {f.key: f for f in FieldDefinition.objects.filter(category=category)}
        values = (data.get("values") or {})
        missing = [k for k, fd in defs.items() if fd.required and k not in values]
        if missing:
            raise serializers.ValidationError({"values": f"Missing required fields: {', '.join(missing)}"})
        for k, v in values.items():
            fd = defs.get(k)
            if not fd: raise serializers.ValidationError({"values": f"Unknown field '{k}'."})
            t = fd.type.key
            if t in ("number","currency") and not isinstance(v, (int, float)):
                raise serializers.ValidationError({k: "Must be a number"})
            if t in ("text","textarea","select") and not isinstance(v, str):
                raise serializers.ValidationError({k: "Must be a string"})
            if t == "multiselect" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise serializers.ValidationError({k: "Must be a list of strings"})
            if fd.validation:
                val = fd.validation
                if "minimum" in val and isinstance(v, (int,float)) and v < val["minimum"]:
                    raise serializers.ValidationError({k: f"Must be ≥ {val['minimum']}"})
                if "maximum" in val and isinstance(v, (int,float)) and v > val["maximum"]:
                    raise serializers.ValidationError({k: f"Must be ≤ {val['maximum']}"})

        # media
        images = data.get("images") or []
        if len(images) > MAX_IMAGES:
            raise serializers.ValidationError({"images": f"Max {MAX_IMAGES} images allowed"})
        if isinstance(data.get("video"), str) and not data["video"]:
            data["video"] = None
        return data

    def create(self, validated):
        user = self.context["request"].user
        category = validated["category"]
        ad = Ad.objects.create(
            owner=user, category=category,
            title=validated.get("title",""),
            price=validated.get("price"),
            city=validated.get("city",""),
            status="draft"
        )
        # values
        values = validated.get("values") or {}
        if values:
            defs = {f.key: f for f in FieldDefinition.objects.filter(category=category)}
            AdFieldValue.objects.bulk_create([
                AdFieldValue(ad=ad, field=defs[k], value=v) for k, v in values.items()
            ])
        # media
        images = validated.get("images") or []
        if images:
            AdMedia.objects.bulk_create([
                AdMedia(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=i) for i, u in enumerate(images)
            ])
        video = validated.get("video")
        if video:
            if AdMedia.objects.filter(ad=ad, kind=AdMedia.VIDEO).exists():
                raise serializers.ValidationError({"video": "Only one video is allowed per ad"})
            AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=video, order_index=0)
        return ad

class AdUpdateSerializer(serializers.Serializer):
    title  = serializers.CharField(max_length=200, required=False, allow_blank=True)
    price  = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2)
    city   = serializers.CharField(max_length=100, required=False, allow_blank=True)
    images = serializers.ListField(child=serializers.URLField(), required=False)
    video  = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    values = serializers.DictField(child=serializers.JSONField(), required=False)

    def update(self, ad: Ad, validated):
        for f in ("title","price","city"):
            if f in validated: setattr(ad, f, validated[f])
        ad.save()

        if "values" in validated:
            existing = {v.field.key: v for v in ad.values.select_related("field")}
            defs = {f.key: f for f in FieldDefinition.objects.filter(category=ad.category)}
            to_create, to_update = [], []
            for key, val in (validated["values"] or {}).items():
                fd = defs.get(key)
                if not fd: continue
                if key in existing:
                    ev = existing[key]; ev.value = val; to_update.append(ev)
                else:
                    to_create.append(AdFieldValue(ad=ad, field=fd, value=val))
            if to_create: AdFieldValue.objects.bulk_create(to_create)
            if to_update: AdFieldValue.objects.bulk_update(to_update, ["value","updated_at"])

        if "images" in validated:
            images = validated.get("images") or []
            if len(images) > MAX_IMAGES:
                raise serializers.ValidationError({"images": f"Max {MAX_IMAGES} images allowed"})
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            AdMedia.objects.bulk_create([
                AdMedia(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=i) for i, u in enumerate(images)
            ])

        if "video" in validated:
            v = validated.get("video")
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            if v:
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)
        return ad

# ---- read ----
class AdDetailSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(read_only=True, slug_field="key")
    values   = serializers.SerializerMethodField()
    images   = serializers.SerializerMethodField()
    video    = serializers.SerializerMethodField()
    class Meta:
        model = Ad
        fields = ["id","code","category","title","price","city","status",
                  "created_at","published_at","values","images","video"]
    def get_values(self, ad): return {v.field.key: v.value for v in ad.values.select_related("field")}
    def get_images(self, ad): return list(ad.media.filter(kind=AdMedia.IMAGE).order_by("order_index").values_list("url", flat=True))
    def get_video(self, ad):
        v = ad.media.filter(kind=AdMedia.VIDEO).first()
        return v.url if v else None

class PublicAdSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(read_only=True, slug_field="key")
    values   = serializers.SerializerMethodField()
    images   = serializers.SerializerMethodField()
    video    = serializers.SerializerMethodField()
    class Meta:
        model = Ad
        fields = ["code","category","title","price","city","published_at","values","images","video"]
    def get_values(self, ad):
        out = {}
        for v in ad.values.select_related("field"):
            if v.field.visible_public: out[v.field.key] = v.value
        return out
    def get_images(self, ad): return list(ad.media.filter(kind=AdMedia.IMAGE).order_by("order_index").values_list("url", flat=True))
    def get_video(self, ad):
        v = ad.media.filter(kind=AdMedia.VIDEO).first()
        return v.url if v else None
