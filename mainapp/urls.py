# urls.py
from django.contrib import admin
from django.urls import path
from mainapp import views as v   # 👈 avoid wildcard imports

app_name = "mainapp"

urlpatterns = [
    # Auth
    path("api/auth/register",  v.RegisterView.as_view(), name="auth-register"),
    path("api/auth/login",     v.LoginView.as_view(),    name="auth-login"),
    path("api/auth/send-otp",  v.SendOTPView.as_view(),  name="auth-send-otp"),
    path("api/auth/verify-otp",v.VerifyOTPView.as_view(),name="auth-verify-otp"),
    path("home",               v.home,                   name="home"),

    # Profile
    path("api/profile/me",     v.MeProfileView.as_view(), name="profile-me"),
    path("api/logout/",        v.logout,                  name="auth-logout"),

    # Ads (create/edit/publish)
    path("api/ads/create",     v.CreateAdView.as_view(),   name="ads-create"),
    path("api/ads/update",     v.UpdateAdView.as_view(),   name="ads-update"),
    path("api/ads/publish",    v.PublishAdView.as_view(),  name="ads-publish"),
    path("api/ads/unpublish",  v.UnpublishAdView.as_view(),name="ads-unpublish"),

    # My ads
    path("api/ads/mine",       v.MyAdsListView.as_view(),   name="ads-mine"),      # NOTE: your view expects POST
    path("api/ads/by-token",   v.MyAdsByTokenView.as_view(),name="ads-by-token"),  # expects POST {token}
    path("api/ads/form",       v.AdFormView.as_view(),      name="ads-form"),      # GET schema / POST save

    # Public ad API
    path("api/public/ads/<slug:code>", v.PublicAdByCodeView.as_view(), name="public-ad-by-code"),

    # Media management
    path("api/ads/media",      v.AdMediaView.as_view(),     name="ad-media"),

    # Public pages
    path("ads/<slug:code>/",         v.ad_public_page_by_code, name="ad_public_page_by_code"),
    path("ads/id/<int:ad_id>/",      v.ad_public_page_by_id,   name="ad_public_page_by_id"),

    # QR
    path("api/qr/claim",       v.ClaimQRView.as_view(),    name="qr-claim"),
    path("api/qr/activate",    v.ActivateQRView.as_view(), name="qr-activate"),
    path("qr/<slug:code>/",    v.qr_landing,               name="qr-landing"),
]
