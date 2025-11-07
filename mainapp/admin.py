from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import FieldType, AdCategory, FieldDefinition, Ad, AdFieldValue, AdMedia, Profile,QRCode,QRScanLog
from django.utils.html import format_html

# --- Profile as its own model (sidebar) ---
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "name", "phone", "is_verified", "masked_op_code", "updated_at")
    search_fields = ("user__username", "user__email", "phone", "name")
    list_filter   = ("is_verified",)
    readonly_fields = ("updated_at",)

    def masked_op_code(self, obj):
        # avoid showing OTP in plaintext
        return f"***{obj.op_code[-2:]}" if obj.op_code else "-"
    masked_op_code.short_description = "OTP"

# --- Inline profile on the User edit page ---
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = "user"
    verbose_name_plural = "Profile"

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

    # Use proper User fields; add a method to display Profile.name if you like
    list_display = ("username", "email", "first_name", "last_name", "profile_name", "is_staff", "is_superuser")
    list_filter  = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "first_name", "last_name", "profile__name")

    def profile_name(self, obj):
        return getattr(getattr(obj, "profile", None), "name", "")
    profile_name.short_description = "Profile name"

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
    @admin.display(description="QR Link")
    def qr_public_link(self, obj):
        q = getattr(obj, "qr_code", None)
        if not q:
            return "-"
        return format_html('<a href="{}" target="_blank">{}</a>', q.public_url, q.public_path)
# admin.py

# admin.py
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .models import QRCode
from .helperUtilis.admin_utils import export_qr_excel_response

@admin.action(description="Export Unassigned/Inactive QR codes to Excel")
def export_unassigned_or_inactive(modeladmin, request, queryset):
    # Export ALL that match (ignore selection) – easiest for users
    qs = QRCode.objects.filter(Q(is_assigned=False) | Q(is_activated=False)).order_by("code")
    return export_qr_excel_response(qs, filename_prefix="qr-unassigned-or-inactive")
@admin.action(description="Export Unassigned QR codes to Excel")
def export_unassigned(modeladmin, request, queryset):
    # Strict version (no ad linked at all):
    # qs = QRCode.objects.filter(ad__isnull=True).order_by("code")

    # Or use your flag:
    qs = QRCode.objects.filter(is_assigned=False).order_by("code")

    return export_qr_excel_response(qs, filename_prefix="qr-unassigned")



@admin.action(description="Export Not Activated QR codes to Excel")
def export_not_activated(modeladmin, request, queryset):
    qs = QRCode.objects.filter(is_activated=False).order_by("code")
    return export_qr_excel_response(qs, filename_prefix="qr-not-activated")

@admin.action(description="Export first 100 Unassigned QR codes to Excel")
def export_first_100_unassigned(modeladmin, request, queryset):
    qs = QRCode.objects.filter(is_assigned=False).order_by("code")[:100]
    return export_qr_excel_response(qs, filename_prefix="qr-unassigned-top100")



@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "batch", "ad", "is_assigned", "is_activated", "scans_count", "last_scan_at", "public_link")
    list_filter  = ("batch", "is_assigned", "is_activated")
    search_fields = ("code", "batch", "ad__code")
    readonly_fields = ("public_link",)

    actions = [export_unassigned,export_not_activated,export_first_100_unassigned]  # 👈 add it here
    actions_on_top = True          # nice UX
    actions_selection_counter = False

    @admin.display(description="Public URL")
    def public_link(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.public_url, obj.public_path)


@admin.register(QRScanLog)
class QRScanLogAdmin(admin.ModelAdmin):
    list_display = ("qr", "ad", "scanned_at", "ip")
    list_filter  = ("scanned_at",)
    search_fields = ("qr__code", "ad__code", "ip", "user_agent")


# notifications/admin.py
from django.contrib import admin
from .models import Notification
from .models import Profile  # ✅ adjust the import path to where your Profile is
from .helperUtilis.onesignal_client import send_push_notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "sent", "created_at")
    actions = ["send_selected_notifications"]

    def send_selected_notifications(self, request, queryset):
        for notification in queryset.filter(sent=False):
            try:
                profile = Profile.objects.get(user=notification.user)
                if profile.player_id:
                    send_push_notification([profile.player_id], notification.title, notification.message)
                    notification.sent = True
                    notification.save()
                else:
                    self.message_user(request, f"⚠️ No player_id for {notification.user.username}", level="warning")
            except Profile.DoesNotExist:
                self.message_user(request, f"❌ No profile found for {notification.user.username}", level="error")

        self.message_user(request, "✅ Notifications sent successfully!")
    send_selected_notifications.short_description = "Send selected notifications"
