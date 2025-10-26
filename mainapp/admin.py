from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import FieldType, AdCategory, FieldDefinition, Ad, AdFieldValue, AdMedia, Profile

# --- Profile as its own model (so it shows in the sidebar) ---
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "name", "phone", "is_verified", "op_code", "updated_at")
    search_fields = ("user__username", "user__email", "phone", "name")
    list_filter   = ("is_verified",)
    readonly_fields = ("updated_at",)

# --- Inline profile on the User edit page ---
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = "user"
    verbose_name_plural = "Profile"

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ("username", "email", "name", "last_name", "is_staff", "is_superuser")
    list_filter  = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "name", "last_name")

# unregister + re-register User with the inline
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)

# ---- your existing registrations ----
@admin.register(FieldType)
class FieldTypeAdmin(admin.ModelAdmin):
    list_display = ("key","name")
    search_fields = ("key","name")

@admin.register(AdCategory)
class AdCategoryAdmin(admin.ModelAdmin):
    list_display = ("key","name_en","name_ar")
    search_fields = ("key","name_en","name_ar")

@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("category","key","type","required","order_index","visible_public")
    list_filter  = ("category","type","required","visible_public")
    search_fields = ("key","label_en","label_ar")
    ordering = ("category","order_index")

class AdFieldValueInline(admin.TabularInline):
    model = AdFieldValue
    extra = 0

class AdMediaInline(admin.TabularInline):
    model = AdMedia
    extra = 0
    fields = ("kind","url","order_index")

@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = ("code","title","status","owner","category","price","city","created_at")
    list_filter  = ("status","category","city")
    search_fields= ("code","title","owner__username")
    inlines = [AdMediaInline, AdFieldValueInline]
from django.contrib import admin
from .models import QRCode, QRScanLog

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "batch", "ad", "is_assigned", "is_activated", "scans_count", "last_scan_at")
    list_filter  = ("batch", "is_assigned", "is_activated")
    search_fields = ("code", "batch", "ad__code")

@admin.register(QRScanLog)
class QRScanLogAdmin(admin.ModelAdmin):
    list_display = ("qr", "ad", "scanned_at", "ip")
    list_filter  = ("scanned_at",)
    search_fields = ("qr__code", "ad__code", "ip", "user_agent")
