from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from.views import FreelancerReadOnlyViewSet,FreelancerWriteViewSet






urlpatterns = [
     path('auth/register/', views.RegisterView.as_view(), name='register'),
     path('verify-email/<str:uidb64>/<str:token>/',views.VerifyEmailView.as_view(), name='verify-email'),
     path('auth/resend-verification/',views.ResendVerificationView.as_view(), name='resend-verification'),
     path('auth/login/', views.LoginView.as_view(), name='login'),
     path('auth/logout/', views.LogoutView.as_view(), name='logout'),
     path('auth/password-change/',views.PasswordChangeView.as_view(), name='password-change'),
     path('auth/password-reset/', views.PasswordResetRequestView.as_view(),name='password-reset-request'),
     path('auth/password-reset-confirm/<str:uidb64>/<str:token>/',views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),

     path('freelance/', include('api.accounts.urls_freelancer')),
     path('clients/', include('api.accounts.urls_client')),
     path('', include('api.accounts.urls_accounts')),

]

