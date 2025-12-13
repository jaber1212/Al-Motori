from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, ErrorDetail

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)  # ✅ added
    
    is_verified = models.BooleanField(default=False)
    op_code = models.CharField(max_length=6, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    player_id = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.phone})"



from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
import secrets, string

# ---- Field types (UI/input kinds) ----
class FieldType(models.Model):
    key = models.SlugField(unique=True)        # text, textarea, number, date, select, multiselect, currency, boolean
    name = models.CharField(max_length=50)
    config = models.JSONField(blank=True, null=True)  # optional UI/validation hints
    def __str__(self): return self.key

# ---- Categories & Field definitions ----
class AdCategory(models.Model):
    key = models.SlugField(unique=True)        # "cars"
    name_en = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80, blank=True, null=True)
    def __str__(self): return self.key

class CarMake(models.Model):
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    def clean(self):
        self.name_en = self.name_en.strip()
        if CarMake.objects.exclude(pk=self.pk).filter(
            name_en__iexact=self.name_en
        ).exists():
            raise ValidationError("Make already exists.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_en



from django.core.exceptions import ValidationError

class CarModel(models.Model):
    make = models.ForeignKey(
        CarMake,
        on_delete=models.CASCADE,
        related_name="models"
    )
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("make", "name_en")

    def clean(self):
        self.name_en = self.name_en.strip()
        if CarModel.objects.exclude(pk=self.pk).filter(
            make=self.make,
            name_en__iexact=self.name_en
        ).exists():
            raise ValidationError("Model already exists for this make.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.make.name_en} - {self.name_en}"


class FieldDefinition(models.Model):
    category = models.ForeignKey(AdCategory, on_delete=models.CASCADE, related_name='fields')
    key = models.SlugField()                                # 'year', 'make', 'model', ...
    type = models.ForeignKey(FieldType, on_delete=models.PROTECT)
    label_en = models.CharField(max_length=120)
    label_ar = models.CharField(max_length=120, blank=True, null=True)
    required = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0, db_index=True)
    visible_public = models.BooleanField(default=True)
    choices = models.JSONField(blank=True, null=True)       # ["Auto","Manual"] or [{"value":"auto","label_en":"Auto"}]
    validation = models.JSONField(blank=True, null=True)    # {"minimum":1980,"maximum":2030}
    placeholder_en = models.CharField(max_length=120, blank=True, null=True)
    placeholder_ar = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        unique_together = ('category', 'key')
        ordering = ['order_index', 'key']
    def __str__(self): return f"{self.category.key}.{self.key}"

# ---- Ads ----
def _gen_code(prefix="AM"):
    alphabet = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(6))}"

class Ad(models.Model):
    STATUS = (("draft","Draft"),("published","Published"),("archived","Archived"))
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ads')
    code  = models.CharField(max_length=16, unique=True, db_index=True)
    category = models.ForeignKey(AdCategory, on_delete=models.PROTECT)

    # denormalized quick filters
    title = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    city  = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=12, choices=STATUS, default="draft", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            for _ in range(6):
                c = _gen_code("AM")
                if not Ad.objects.filter(code=c).exists():
                    self.code = c
                    break
        return super().save(*args, **kwargs)
    def __str__(self): return self.code

# ---- Dynamic field values (one row per field per ad) ----
class AdFieldValue(models.Model):
    ad    = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name='values')
    field = models.ForeignKey(FieldDefinition, on_delete=models.CASCADE, related_name='ad_values')
    value = models.JSONField(default=dict, blank=True, null=True)
    locale = models.CharField(max_length=5, blank=True, null=True)  # optional 'en'/'ar'
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('ad','field','locale')
        indexes = [models.Index(fields=['ad','field'])]
    def __str__(self): return f"{self.ad.code}:{self.field.key}={self.value}"

# ---- Media (many images, max 1 video) ----
class AdMedia(models.Model):
    IMAGE, VIDEO = "image", "video"
    KIND_CHOICES = [(IMAGE,"Image"), (VIDEO,"Video")]
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="media")
    kind = models.CharField(max_length=5, choices=KIND_CHOICES, db_index=True)
    url  = models.URLField(max_length=500)
    order_index = models.PositiveIntegerField(default=0, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["ad","kind","order_index"])]
        constraints = [
            models.UniqueConstraint(fields=["ad"], condition=Q(kind="video"), name="unique_video_per_ad")
        ]
    def __str__(self): return f"{self.ad.code}:{self.kind}@{self.order_index}"



from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from .models import Ad  # your existing Ad model

class QRCode(models.Model):
    code = models.CharField(max_length=24, unique=True, db_index=True)  # printed code
    batch = models.CharField(max_length=50, blank=True, null=True)      # optional: printing batch label
    ad = models.OneToOneField(Ad, on_delete=models.SET_NULL, null=True, blank=True, related_name="qr_code")

    is_assigned = models.BooleanField(default=False)   # got linked to an Ad
    is_activated = models.BooleanField(default=False)  # first app scan completed activation
    first_scan_at = models.DateTimeField(null=True, blank=True)
    scans_count = models.PositiveIntegerField(default=0)
    last_scan_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["batch"]),
            models.Index(fields=["is_assigned", "is_activated"]),
        ]

    @property
    def public_path(self) -> str:
        return build_qr_public_path(self.code)

    @property
    def public_url(self) -> str:
        return build_qr_public_url(self.code)
    def __str__(self):
        return self.code

    def mark_scanned(self):
        now = timezone.now()
        if not self.first_scan_at:
            self.first_scan_at = now
        self.scans_count += 1
        self.last_scan_at = now
        self.save(update_fields=["first_scan_at", "scans_count", "last_scan_at"])


class QRScanLog(models.Model):
    qr = models.ForeignKey(QRCode, on_delete=models.CASCADE, related_name="logs")
    ad = models.ForeignKey(Ad, on_delete=models.SET_NULL, null=True, blank=True, related_name="qr_logs")
    scanned_at = models.DateTimeField(auto_now_add=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    referrer = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.qr.code} @ {self.scanned_at}"

# core/utils.py  (create this if you don’t have it)
from django.conf import settings
from django.urls import reverse, NoReverseMatch
PUBLIC_BASE_URL = "https://aimotoria.com"   # or "" for relative links
QR_URL_NAME = "qr_landing"
def build_qr_public_path(code: str) -> str:
    """
    Returns the path like '/qr/ABC123' or the reversed named route if available.
    """
    url_name = QR_URL_NAME
    if url_name:
        try:
            return reverse(url_name, args=[code])
        except NoReverseMatch:
            pass
    return f"/qr/{code}"

def build_qr_public_url(code: str) -> str:
    """
    Returns absolute URL if PUBLIC_BASE_URL is set, else just the path.
    """
    path = build_qr_public_path(code)
    base = PUBLIC_BASE_URL
    if base.endswith("/"):
        base = base[:-1]
    return f"{base}{path}"


# models.py
# notifications/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.models import User
from django.contrib import admin
from .helperUtilis.onesignal_client import send_push_notification
from mainapp.models import Profile  # adjust import path as needed

class Notification(models.Model):
    TARGET_CHOICES = [
        ("single", "Single User"),
        ("all", "All Users"),
    ]

    target = models.CharField(max_length=10, choices=TARGET_CHOICES, default="single")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)

    def __str__(self):
        if self.target == "all":
            return f"{self.title} → All Users"
        return f"{self.title} → {self.user.username if self.user else 'N/A'}"
