from django.urls import path
from .views import PaymentInitiateView, PaymentCallbackView

urlpatterns = [
    path('initiate/', PaymentInitiateView.as_view(), name='api_initiate_payment'),
    path('callback/', PaymentCallbackView.as_view(), name='api_payment_callback'),
]
