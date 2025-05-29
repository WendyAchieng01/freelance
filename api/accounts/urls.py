from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from . import views


router = DefaultRouter()

router.register(r'users', views.UserViewSet, basename='user')
router.register(r'profiles', views.ProfileViewSet, basename='profile')
router.register(r'skills', views.SkillViewSet, basename='skill')
router.register(r'languages', views.LanguageViewSet, basename='language')





urlpatterns = [
     path('auth/register/', views.RegisterView.as_view(), name='register'),
     path('verify-email/<str:uidb64>/<str:token>/',views.VerifyEmailView.as_view(), name='verify-email'),
     path('auth/resend-verification/<int:user_id>/',views.ResendVerificationView.as_view(), name='resend-verification'),
     path('auth/login/', views.LoginView.as_view(), name='login'),
     path('auth/logout/', views.LogoutView.as_view(), name='logout'),
     path('auth/password-change/',views.PasswordChangeView.as_view(), name='password-change'),
     path('auth/password-reset/', views.PasswordResetRequestView.as_view(),name='password-reset-request'),
     path('password-reset-confirm/<str:uidb64>/<str:token>/',views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
     # Forms
     path('freelancer-form/', views.FreelancerFormView.as_view(), name='freelancer-form'),
     path('client-form/', views.ClientFormView.as_view(), name='client-form'),
     path('frelancers/', views.ListFreelancersView.as_view(), name='list-freelancers'),
     path('clients/', views.ClientListView.as_view(), name='list-clients'),
     # Resources
     path('', include(router.urls)),
]
