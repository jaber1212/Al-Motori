# urls.py
from django.urls import path
from mainapp.views.authViews import *
from mainapp.views.coreViews import *  # 👈 avoid wildcard imports
from mainapp.views.webViews import *  # 👈 avoid wildcard imports

app_name = "mainapp"

urlpatterns = [
    # Auth
    path("home", home, name="home"),

    path("api/auth/register",  RegisterView.as_view(), name="auth-register"),
    path("api/auth/login",     LoginView.as_view(),    name="auth-login"),
    path("api/auth/send-otp",  SendOTPView.as_view(),  name="auth-send-otp"),
    path("api/auth/verify-otp",VerifyOTPView.as_view(),name="auth-verify-otp"),

    # Profile
    path("api/profile/me",     MeProfileView.as_view(), name="profile-me"),
    path("api/logout/",        logout,                  name="auth-logout"),

    # Ads (create/edit/publish)
    path("api/ads/create",     CreateAdView.as_view(),   name="ads-create"),
    path("api/ads/update",     UpdateAdView.as_view(),   name="ads-update"),
    path("api/ads/publish",    PublishAdView.as_view(),  name="ads-publish"),
    path("api/ads/unpublish",  UnpublishAdView.as_view(),name="ads-unpublish"),

    # My ads
    path("api/ads/mine",       MyAdsListView.as_view(),   name="ads-mine"),      # NOTE: your view expects POST
    path("api/ads/by-token",   MyAdsByTokenView.as_view(),name="ads-by-token"),  # expects POST {token}
    path("api/ads/form",       AdFormView.as_view(),      name="ads-form"),      # GET schema / POST save

    # Public ad API
    path("api/public/ads/<slug:code>", PublicAdByCodeView.as_view(), name="public-ad-by-code"),

    # Media management
    path("api/ads/media",      AdMediaView.as_view(),     name="ad-media"),

    # Public pages
    path("ads/<slug:code>/",         ad_public_page_by_code, name="ad_public_page_by_code"),
    path("ads/id/<int:ad_id>/",      ad_public_page_by_id,   name="ad_public_page_by_id"),

    # QR
    path("api/qr/claim",       ClaimQRView.as_view(),    name="qr-claim"),
    path("api/qr/activate",    ActivateQRView.as_view(), name="qr-activate"),
    path("qr/<slug:code>/",    qr_landing,               name="qr-landing"),

    path('terms/', terms_view, name='terms'),
    path('', home_landing, name='terms'),

    path('privacy/', privacy_view, name='privacy'),
]
