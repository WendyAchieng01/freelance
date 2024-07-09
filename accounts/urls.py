from django.urls import include, path
from . import views

app_name = 'accounts'
urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("update_user/", views.update_user, name="update_user"),
    path("update_password/", views.update_password, name="update_password"),
    path("update_info/", views.update_info, name="update_info"),
    path("client/update_user/", views.client_update_user, name="client_update_user"),
    path("client/update_password/", views.client_update_password, name="client_update_password"),
    path("client/update_info/", views.client_update_info, name="client_update_info"),
    path('freelancer_form/<int:user_id>/', views.freelancer_form, name='freelancer_form'),
    path('client_form/<int:user_id>/', views.client_form, name='client_form'),
    path('update-profile-pic/', views.update_profile_pic, name='update_profile_pic'),
    # Add the empty path at the end
    path("", views.signup, name="signup"),
]