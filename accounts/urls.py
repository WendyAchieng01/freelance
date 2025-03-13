from django.urls import include, path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'accounts'
urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    path('resend-verification/<int:user_id>/', views.resend_verification, name='resend_verification'),
    path("accounts/", include("django.contrib.auth.urls")),
    path("update_password/", views.update_password, name="update_password"),
    path("client/update_password/", views.client_update_password, name="client_update_password"),
    path('freelancer_form/<int:user_id>/', views.freelancer_form, name='freelancer_form'),
    path('client_form/<int:user_id>/', views.client_form, name='client_form'),
    path('update-profile-pic/', views.update_profile_pic, name='update_profile_pic'),
    path('portfolio/freelancer/<int:user_id>/', views.freelancer_portfolio, name='freelancer_portfolio'),
    path('portfolio/client/<int:user_id>/', views.client_portfolio, name='client_portfolio'),
    path('update-email/<int:user_id>/', views.update_email, name='update_email'),
    path('profile_creation/', views.profile_creation, name='profile_creation'),

    path("", views.signup, name="signup"),
]