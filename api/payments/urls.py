from django.urls import path, include
from .views import InitiatePayment, PaymentStatus,payment_success,payment_cancel

urlpatterns = [
    path('initiate/', InitiatePayment.as_view(), name='initiate_payment'),
    path('<int:payment_id>/', PaymentStatus.as_view(), name='payment_status'),
    path('paypal-ipn/', include('paypal.standard.ipn.urls'), name='paypal-ipn'),
    path('payments/success/', payment_success, name='payment_success'),
    path('payments/cancel/', payment_cancel, name='payment_cancel'),
]
