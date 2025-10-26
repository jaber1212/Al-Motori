# mainapp/serializers/coreSerializers.py
from __future__ import annotations

from rest_framework import serializers
from mainapp.models import (
    Ad, AdCategory, FieldType, FieldDefinition, AdFieldValue, AdMedia, QRCode
)

MAX_IMAGES = 12


# ---------- Schema (for mobile / web forms) ----------

class FieldTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldType
        fields = ["key", "name", "config"]


class FieldDefinitionSerializer(serializers.ModelSerializer):
    type = FieldTypeSerializer(read_only=True)

    class Meta:
        model = FieldDefinition
        fields = [
            "key", "type", "label_en", "label_ar", "required",
            "order_index", "visible_public", "choices", "validation",
            "placeholder_en", "placeholder_ar",
        ]


class CategorySchemaSerializer(serializers.ModelSerializer):
    fields = FieldDefinitionSerializer(many=True, read_only=True)

    class Meta:
        model = AdCategory
        fields = ["key", "name_en", "name_ar", "fields"]


# ---------- Public field (lean) ----------

class PublicFieldSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="type.key")

    class Meta:
        model = FieldDefinition
        fields = (
            "key", "type", "label_en", "label_ar", "required",
            "order_index", "visible_public", "choices", "validation",
            "placeholder_en", "placeholder_ar",
        )


# ---------- Create / Update ----------

class AdCreateSerializer(serializers.Serializer):
    category = serializers.SlugRelatedField(slug_field="key", queryset=AdCategory.objects.all())
    title    = serializers.CharField(max_length=200, required=False, allow_blank=True)
    price    = serializers.DecimalField(required=False, allow_null=True, max_digits=12, decimal_places=2)
    city     = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # If client POSTs hosted media (no file uploads)
    images = serializers.ListField(child=serializers.URLField(), required=False, allow_empty=True)
    video  = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    # Dynamic fields by key
    values = serializers.DictField(child=serializers.JSONField(), required=False)

    def validate(self, data):
        # Dynamic fields validation
        category = data["category"]
        defs = {f.key: f for f in FieldDefinition.objects.filter(category=category)}
        values = data.get("values") or {}

        missing = [k for k, fd in defs.items() if fd.required and k not in values]
        if missing:
            raise serializers.ValidationError({"values": f"Missing required fields: {', '.join(missing)}"})

        for k, v in values.items():
            fd = defs.get(k)
            if not fd:
                raise serializers.ValidationError({"values": f"Unknown field '{k}'."})

            t = fd.type.key if fd.type else "text"
            if t in ("number", "currency") and not isinstance(v, (int, float)):
                raise serializers.ValidationError({k: "Must be a number"})
            if t in ("text", "textarea", "select") and not isinstance(v, str):
                raise serializers.ValidationError({k: "Must be a string"})
            if t == "multiselect" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise serializers.ValidationError({k: "Must be a list of strings"})

            # extra validation JSON on the FieldDefinition
            if fd.validation:
                val = fd.validation
                if "minimum" in val and isinstance(v, (int, float)) and v < val["minimum"]:
                    raise serializers.ValidationError({k: f"Must be ≥ {val['minimum']}"})
                if "maximum" in val and isinstance(v, (int, float)) and v > val["maximum"]:
                    raise serializers.ValidationError({k: f"Must be ≤ {val['maximum']}"})

        # Media limits (URLs mode)
        images = data.get("images") or []
        if len(images) > MAX_IMAGES:
            raise serializers.ValidationError({"images": f"Max {MAX_IMAGES} images allowed"})

        # Tighten video empty to None
        if isinstance(data.get("video"), str) and not data["video"]:
            data["video"] = None

        return data

    def create(self, validated):
        user = self.context["request"].user
        category = validated["category"]
        ad = Ad.objects.create(
            owner=user, category=category,
            title=validated.get("title", ""),
            price=validated.get("price"),
            city=validated.get("city", ""),
            status="draft",
        )

        # Dynamic values
        values = validated.get("values") or {}
        if values:
            defs = {f.key: f for f in FieldDefinition.objects.filter(category=category)}
            AdFieldValue.objects.bulk_create([
                AdFieldValue(ad=ad, field=defs[k], value=v) for k, v in values.items()
                if k in defs
            ])

        # Media (URLs path)
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
        # Core
        for f in ("title", "price", "city"):
            if f in validated:
                setattr(ad, f, validated[f])
        ad.save()

        # Dynamic
        if "values" in validated:
            existing = {v.field.key: v for v in ad.values.select_related("field")}
            defs = {f.key: f for f in FieldDefinition.objects.filter(category=ad.category)}
            to_create, to_update = [], []
            for key, val in (validated["values"] or {}).items():
                fd = defs.get(key)
                if not fd:
                    continue
                if key in existing:
                    ev = existing[key]
                    ev.value = val
                    to_update.append(ev)
                else:
                    to_create.append(AdFieldValue(ad=ad, field=fd, value=val))
            if to_create:
                AdFieldValue.objects.bulk_create(to_create)
            if to_update:
                AdFieldValue.objects.bulk_update(to_update, ["value", "updated_at"])

        # Images (URLs mode)
        if "images" in validated:
            images = validated.get("images") or []
            if len(images) > MAX_IMAGES:
                raise serializers.ValidationError({"images": f"Max {MAX_IMAGES} images allowed"})
            ad.media.filter(kind=AdMedia.IMAGE).delete()
            AdMedia.objects.bulk_create([
                AdMedia(ad=ad, kind=AdMedia.IMAGE, url=u, order_index=i) for i, u in enumerate(images)
            ])

        # Video (URLs mode)
        if "video" in validated:
            v = validated.get("video")
            ad.media.filter(kind=AdMedia.VIDEO).delete()
            if v:
                AdMedia.objects.create(ad=ad, kind=AdMedia.VIDEO, url=v, order_index=0)

        return ad


# ---------- Read serializers ----------

class AdDetailSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(read_only=True, slug_field="key")
    values   = serializers.SerializerMethodField()
    images   = serializers.SerializerMethodField()
    video    = serializers.SerializerMethodField()

    class Meta:
        model = Ad
        fields = [
            "id", "code", "category", "title", "price", "city", "status",
            "created_at", "published_at", "values", "images", "video",
        ]

    def get_values(self, ad):
        return {v.field.key: v.value for v in ad.values.select_related("field")}

    def get_images(self, ad):
        return list(ad.media.filter(kind=AdMedia.IMAGE).order_by("order_index").values_list("url", flat=True))

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
        fields = ["code", "category", "title", "price", "city", "published_at", "values", "images", "video"]

    def get_values(self, ad):
        out = {}
        for v in ad.values.select_related("field"):
            if v.field.visible_public:
                out[v.field.key] = v.value
        return out

    def get_images(self, ad):
        return list(ad.media.filter(kind=AdMedia.IMAGE).order_by("order_index").values_list("url", flat=True))

    def get_video(self, ad):
        v = ad.media.filter(kind=AdMedia.VIDEO).first()
        return v.url if v else None


# ---------- QR serializers ----------

class ClaimQRSerializer(serializers.Serializer):
    ad_id = serializers.IntegerField()
    code  = serializers.CharField(max_length=24)


class ActivateQRSerializer(serializers.Serializer):
    ad_id = serializers.IntegerField()
    code  = serializers.CharField(max_length=24)
