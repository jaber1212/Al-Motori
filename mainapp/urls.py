from django.contrib import admin
from django.urls import path,re_path
from mainapp.views import *

urlpatterns = [


    # Auth
    path('api/auth/register', RegisterView.as_view()),
    path('api/auth/login', LoginView.as_view()),
    path('api/auth/send-otp', SendOTPView.as_view()),
    path('api/auth/verify-otp', VerifyOTPView.as_view()),
        path('home', home, name='home'),  # 👈 homepage

    # Profile
    path('api/profile/me', MeProfileView.as_view()),





  path('api/ads/create',  CreateAdView.as_view()),  # POST
    path('api/ads/update',  UpdateAdView.as_view()),  # POST (ad_id in body)
    path('api/ads/publish', PublishAdView.as_view()), # POST (ad_id in body)
    path('api/ads/unpublish', UnpublishAdView.as_view()), # POST (ad_id in body)

    path('api/ads/mine',     MyAdsListView.as_view()),     # GET (Authorization header)
    path('api/ads/by-token', MyAdsByTokenView.as_view()),  # POST {token}
    path("api/ads/form", AdFormView.as_view()),  # GET (schema) + POST (create/edit)

    path('api/public/ads/<str:code>', PublicAdByCodeView.as_view()),  # GET


    path("api/ads/media", AdMediaView.as_view(), name="ad-media"),





    path("ads/<str:code>/", ad_public_page_by_code, name="ad_public_page_by_code"),
    path("ads/id/<int:ad_id>/", ad_public_page_by_id, name="ad_public_page_by_id"),

    path("api/qr/claim",    ClaimQRView.as_view(),    name="qr_claim"),
    path("api/qr/activate", ActivateQRView.as_view(), name="qr_activate"),
    re_path(r"^qr/(?P<code>[A-Za-z0-9\-]+)/?$", qr_landing, name="qr_landing"),

    path("ads/<int:ad_id>/", ad_public_redirect_by_id, name="ad_public_redirect_by_id"),
re_path(r"^ads/(?P<code>(?!\d+$)[A-Za-z0-9\-]+)/$", ad_public_page_by_code, name="ad_public_by_code")

]
