# editor_admin.py

from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import AdminSite, ModelAdmin, TabularInline, SimpleListFilter
from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

from .models import Ad, AdMedia, AdFieldValue

from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .models import QRCode
from .helperUtilis.admin_utils import export_qr_excel_response

# ----------------------
# Permissions
# ----------------------

def is_editor(user):
    """Allow login to editor site only for Editors and Superusers"""
    return user.is_active and user.is_staff and (
        user.is_superuser or user.groups.filter(name="Editor").exists()
    )


# ----------------------
# Custom Admin Site
# ----------------------

class EditorSite(AdminSite):
    site_header = "Editor Panel"
    site_title = "Editor Panel"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("dashboard/", self.admin_view(self.dashboard_view), name="editor_dashboard"),
        ]
        return custom + urls

    @user_passes_test(is_editor)
    def dashboard_view(self, request):
        qs = Ad.objects.all()
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
        return render(request, "editor/dashboard.html", {"data": data, "recent": recent})


editor_site = EditorSite(name="editor_admin")


# ----------------------
# Filters
# ----------------------

class MineFilter(SimpleListFilter):
    """Allow editors to toggle between 'My ads' and 'All ads'"""
    title = "scope"
    parameter_name = "scope"

    def lookups(self, request, model_admin):
        return (("mine", "My ads"), ("all", "All ads"))

    def queryset(self, request, queryset):
        if request.user.is_superuser:
            return queryset
        scope = self.value()
        if scope == "all":
            return queryset
        return queryset.filter(owner=request.user)


# ----------------------
# Inlines
# ----------------------

class MediaInline(TabularInline):
    model = AdMedia
    extra = 0
    fields = ("kind", "url", "order_index")


class ValuesInline(TabularInline):
    model = AdFieldValue
    extra = 0
    fields = ("field", "value", "updated_at")
    readonly_fields = ("updated_at",)


# ----------------------
# Ad Admin for Editors
# ----------------------

@admin.register(Ad, site=editor_site)
class EditorAdAdmin(ModelAdmin):
    list_display = ("code", "title", "status", "owner", "category", "price", "city", "created_at")
    list_filter = (MineFilter, "status", "category", "city")
    search_fields = ("code", "title", "owner__username")
    inlines = [MediaInline, ValuesInline]
    actions = ["publish_ads", "unpublish_ads"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs  # use MineFilter instead of hard filtering

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    @admin.display(description="QR Link")
    def qr_public_link(self, obj):
        q = getattr(obj, "qr_code", None)
        if not q:
            return "-"
        return format_html('<a href="{}" target="_blank">{}</a>', q.public_url, q.public_path)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
            ro += ["owner", "category", "code", "created_at", "published_at"]
        return ro

    def has_change_permission(self, request, obj=None):
        perm = super().has_change_permission(request, obj)
        if not perm:
            return False
        if obj and request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
            return obj.owner_id == request.user.id
        return True

    def save_model(self, request, obj, form, change):
        if not change and request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
            max_ads = getattr(settings, "EDITOR_MAX_ADS", 200)
            if Ad.objects.filter(owner=request.user).count() >= max_ads:
                raise PermissionDenied(f"Editor quota reached: max {max_ads} ads.")
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if form.instance.pk:
            ad = form.instance
            max_imgs = getattr(settings, "EDITOR_MAX_IMAGES", 12)
            images = ad.media.filter(kind="image").count()
            if images > max_imgs:
                ad.media.filter(kind="image").order_by("-order_index")[max_imgs-1:].delete()
            vids = ad.media.filter(kind="video").order_by("id")
            if vids.count() > 1:
                vids.exclude(pk=vids.first().pk).delete()

    def publish_ads(self, request, queryset):
        updated = 0
        for ad in queryset:
            if request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
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
            if request.user.groups.filter(name="Editor").exists() and not request.user.is_superuser:
                if ad.owner_id != request.user.id:
                    continue
            ad.status = "draft"
            ad.published_at = None
            ad.save(update_fields=["status", "published_at"])
            updated += 1
        self.message_user(request, f"Unpublished {updated} ad(s).")
    unpublish_ads.short_description = "Unpublish selected ads"


@admin.action(description="Export Unassigned/Inactive QR codes to Excel")
def export_unassigned_or_inactive_editor(modeladmin, request, queryset):
    # If you want to restrict editors to their own ads only, uncomment:
    # base = QRCode.objects.filter(Q(is_assigned=False) | Q(is_activated=False))
    # if request.user.is_superuser:
    #     qs = base
    # else:
    #     qs = base.filter(Q(ad__owner=request.user) | Q(ad__isnull=True))
    # return export_qr_excel_response(qs, filename_prefix="qr-unassigned-or-inactive")
    qs = QRCode.objects.filter(Q(is_assigned=False) | Q(is_activated=False)).order_by("code")
    return export_qr_excel_response(qs, filename_prefix="qr-unassigned-or-inactive")

@admin.register(QRCode, site=editor_site)
class EditorQRCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "batch", "ad", "is_assigned", "is_activated", "scans_count", "last_scan_at", "public_link")
    list_filter  = ("batch", "is_assigned", "is_activated")
    search_fields = ("code", "batch", "ad__code")
    readonly_fields = ("public_link",)
    actions = [export_unassigned_or_inactive_editor]

    @admin.display(description="Public URL")
    def public_link(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.public_url, obj.public_path)
