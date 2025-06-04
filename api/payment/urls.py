from django.urls import path
from .views import PaymentInitiateView, PaymentCallbackView,ProceedToPayAPIView


urlpatterns = [
    path('initiate/<slug:slug>/',PaymentInitiateView.as_view(), name='payment-initiate-slug'),
    path('callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('<slug_or_id>/proceed-to-pay/', ProceedToPayAPIView.as_view(), name='proceed-to-pay'),

]
