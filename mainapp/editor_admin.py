# editor_admin.py

from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import (
    AdminSite, ModelAdmin, TabularInline, SimpleListFilter
)
from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.html import format_html

from .models import Ad, AdMedia, AdFieldValue, Profile, QRCode
from .helperUtilis.admin_utils import export_qr_excel_response


# -----------------------------------------
# EDITOR Login Permission
# -----------------------------------------

def is_editor(user):
    """Allow login for Editors or Superusers"""
    return (
        user.is_active and user.is_staff and
        (user.is_superuser or user.groups.filter(name="Editor").exists())
    )


# -----------------------------------------
# Custom Admin Site for EDITOR
# -----------------------------------------

class EditorSite(AdminSite):
    site_header = "Editor Panel"
    site_title = "Editor Panel"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_view(self.dashboard_view),
                name="editor_dashboard"
            ),
        ]
        return custom + urls

    @user_passes_test(is_editor)
    def dashboard_view(self, request):
        qs = Ad.objects.all()

        # Editors see only their ads
        if request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
            qs = qs.filter(owner=request.user)

        now = timezone.now()
        last7 = now - timedelta(days=7)

        data = {
            "total_ads": qs.count(),
            "draft_ads": qs.filter(status="draft").count(),
            "published_ads": qs.filter(status="published").count(),
            "ads_last_7d": qs.filter(created_at__gte=last7).count(),
        }

        recent = qs.order_by("-created_at")[:10]

        return render(request, "editor/dashboard.html", {
            "data": data,
            "recent": recent
        })


editor_site = EditorSite(name="editor_admin")


# -----------------------------------------
# Filters
# -----------------------------------------

class MineFilter(SimpleListFilter):
    title = "scope"
    parameter_name = "scope"

    def lookups(self, request, model_admin):
        return (
            ("mine", "My ads"),
            ("all", "All ads"),
        )

    def queryset(self, request, queryset):
        if request.user.is_superuser:
            return queryset

        scope = self.value()

        if scope == "all":
            return queryset

        return queryset.filter(owner=request.user)


# -----------------------------------------
# Inlines
# -----------------------------------------

class MediaInline(TabularInline):
    model = AdMedia
    extra = 0
    fields = ("kind", "url", "order_index")

    def has_delete_permission(self, request, obj=None):
        return False if request.user.groups.filter(name="Editor").exists() else True


class ValuesInline(TabularInline):
    model = AdFieldValue
    extra = 0
    fields = ("field", "value", "updated_at")
    readonly_fields = ("updated_at",)

    def has_delete_permission(self, request, obj=None):
        return False if request.user.groups.filter(name="Editor").exists() else True


# -----------------------------------------
# Ad Admin (Editor logic)
# -----------------------------------------

@admin.register(Ad, site=editor_site)
class EditorAdAdmin(ModelAdmin):
    list_display = (
        "code", "title", "status", "owner",
        "category", "price", "city", "created_at"
    )
    list_filter = (MineFilter, "status", "category", "city")
    search_fields = ("code", "title", "owner__username")
    inlines = [MediaInline, ValuesInline]
    actions = ["publish_ads", "unpublish_ads"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name="Editor").exists():
            return False
        return True

    def has_change_permission(self, request, obj=None):
        # Editors can modify only their own Ads
        if request.user.groups.filter(name="Editor").exists() and obj:
            return obj.owner_id == request.user.id
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))

        if request.user.groups.filter(name="Editor").exists():
            ro += ["owner", "category", "code", "created_at", "published_at"]

        return ro

    def save_model(self, request, obj, form, change):
        if request.user.groups.filter(name="Editor").exists():
            if not change:  # new ad
                max_ads = getattr(settings, "EDITOR_MAX_ADS", 200)
                if Ad.objects.filter(owner=request.user).count() >= max_ads:
                    raise PermissionDenied("Editor quota reached.")
                obj.owner = request.user

        super().save_model(request, obj, form, change)

    # ----------------- Actions -----------------

    def publish_ads(self, request, queryset):
        updated = 0
        for ad in queryset:
            if request.user.groups.filter(name="Editor").exists():
                if ad.owner_id != request.user.id:
                    continue
            ad.status = "published"
            ad.published_at = timezone.now()
            ad.save(update_fields=["status", "published_at"])
            updated += 1

        self.message_user(request, f"Published {updated} ad(s).")

    publish_ads.short_description = "Publish selected ads"

    def unpublish_ads(self, request, queryset):
        updated = 0
        for ad in queryset:
            if request.user.groups.filter(name="Editor").exists():
                if ad.owner_id != request.user.id:
                    continue
            ad.status = "draft"
            ad.published_at = None
            ad.save(update_fields=["status", "published_at"])
            updated += 1

        self.message_user(request, f"Unpublished {updated} ad(s).")

    unpublish_ads.short_description = "Unpublish selected ads"


# -----------------------------------------
# QR CODE ADMIN
# -----------------------------------------

@admin.action(description="Export Unassigned/Inactive QR codes to Excel")
def export_unassigned_or_inactive_editor(modeladmin, request, queryset):
    qs = QRCode.objects.filter(
        Q(is_assigned=False) | Q(is_activated=False)
    ).order_by("code")

    return export_qr_excel_response(qs, filename_prefix="qr-unassigned-or-inactive")


@admin.register(QRCode, site=editor_site)
class EditorQRCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code", "batch", "ad", "is_assigned",
        "is_activated", "scans_count", "last_scan_at",
        "public_link"
    )
    list_filter = ("batch", "is_assigned", "is_activated")
    search_fields = ("code", "batch", "ad__code")
    readonly_fields = ("public_link",)
    actions = [export_unassigned_or_inactive_editor]

    @admin.display(description="Public URL")
    def public_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            obj.public_url,
            obj.public_path,
        )
