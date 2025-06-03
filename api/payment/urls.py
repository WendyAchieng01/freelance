from django.urls import path
from .views import PaymentInitiateView, PaymentCallbackView,ProceedToPayView


urlpatterns = [
    path('initiate/<slug:slug>/',PaymentInitiateView.as_view(), name='payment-initiate-slug'),
    path('initiate/<int:id>/', PaymentInitiateView.as_view(), name='payment-initiate-id'),
    path('callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('<slug_or_id>/proceed-to-pay/', ProceedToPayView.as_view(), name='proceed-to-pay'),

]
