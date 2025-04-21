from django.urls import path
from . import views
from django.conf.urls import include

app_name = 'payments'

urlpatterns = [
    
    path('initiate-payment/<int:job_id>/<int:response_id>/', views.initiate_response_payment, name='initiate_response_payment'),
    path('successful/<int:job_id>/<int:response_id>/', views.successful_response, name='successful_response'),
    path('cancelled/<int:job_id>/<int:response_id>/', views.cancelled_response, name='cancelled_response'),
    
    path('verify-payment/<int:job_id>/<int:response_id>/', views.verify_payment, name='verify_payment'),

    # IPN endpoint (already included typically via paypal.urls)
    path('paypal-ipn/', include('paypal.standard.ipn.urls'), name='paypal-ipn'),
]