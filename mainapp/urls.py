from django.contrib import admin
from django.urls import path
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
    path("api/ads/form-schema", AdFormSchemaView.as_view()),

    path('api/public/ads/<str:code>', PublicAdByCodeView.as_view()),  # GET









    
]
