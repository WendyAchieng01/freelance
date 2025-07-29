"""
URL configuration for freelance project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from api.accounts.views import PasswordResetConfirmView



urlpatterns = [
    path('api/v1/', include('api.urls')),
    path('auth/password-reset-confirm/<str:uidb64>/<str:token>/',PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('core/', include('core.urls', namespace='core')),
    path('academy/', include('academy.urls', namespace='academy')),
    path('invoice/', include('invoicemgmt.urls', namespace='invoicemgmt')),
    path('payments/', include('payment.urls', namespace='payment')),
    path('payment/', include('payments.urls', namespace='payments')),
    path('admin/', admin.site.urls),
    path('paypal/', include('paypal.standard.ipn.urls')),

    # Password reset paths
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset.html',
             email_template_name='registration/password_reset_email.html',
             success_url='/accounts/password_reset/done/'
         ),
         name='password_reset'),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/accounts/reset/done/'
         ),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('', include('core.urls', namespace='landing_page')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [ path('tz_detect/', include('tz_detect.urls')),]
