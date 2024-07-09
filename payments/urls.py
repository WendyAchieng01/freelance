from django.urls import path, include
from . import views

app_name = 'payments' 

urlpatterns = [
    path('purchase/<int:job_id>/', views.job_purchase, name='job_purchase'),
    path('successful/<int:job_id>/', views.successful, name='successful'),
    path('cancelled/<int:job_id>/', views.cancelled, name='cancelled'),
    path('paypal/', include('paypal.standard.ipn.urls')),
    path('verify-payment/<int:job_id>/', views.verify_payment, name='verify_payment'),
]
