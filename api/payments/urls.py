from django.urls import path
from .views import (
    InitiatePaypalPayment,
    CapturePaypalPayment,
    PaymentStatus,
    PaypalSuccessView,
    PaypalFailedView,
)

app_name = "api.payments"

urlpatterns = [
    path("<slug:slug>/initiate/", InitiatePaypalPayment.as_view(),    name="paypal-initiate",),
    path("<slug:slug>/capture/<str:order_id>/", CapturePaypalPayment.as_view(),     name="paypal-capture",),
    path("<slug:slug>/status/<int:payment_id>/", PaymentStatus.as_view(),      name="paypal-status",),
    path("<slug:slug>/success/<str:invoice>/", PaypalSuccessView.as_view(),     name="paypal-success",),
    path("<slug:slug>/failed/<str:invoice>/", PaypalFailedView.as_view(),      name="paypal-failed",)
]




