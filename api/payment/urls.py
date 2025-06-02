from django.urls import path
from .views import PaymentInitiateView, PaymentCallbackView


urlpatterns = [
    path('payment/initiate/<slug:slug>/',PaymentInitiateView.as_view(), name='payment-initiate-slug'),
    path('payment/initiate/<int:id>/', PaymentInitiateView.as_view(), name='payment-initiate-id'),
    path('payment/callback/', PaymentCallbackView.as_view(), name='payment-callback'),
]
