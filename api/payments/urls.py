from django.urls import path
from . import views

urlpatterns = [
    path('payment/initiate/<int:job_id>/',views.InitiatePaypalPayment.as_view(), name='initiate-by-id'),
    path('payment/initiate/<slug:slug>/',views.InitiatePaypalPayment.as_view(), name='initiate-by-slug'),
    path('payment/status/<int:payment_id>/',views.PaymentStatus.as_view(), name='paypal-status'),
    path("paypal/success/id/<int:job_id>/", views.PaypalSuccessView.as_view(), name="successful_response_by_id"),
    path("paypal/success/slug/<slug:slug>/", views.PaypalSuccessView.as_view(), name="successful_response_by_slug"),
    path("paypal/cancel/id/<int:job_id>/", views.PaypalFailedView.as_view(), name="cancelled_response_by_id"),
    path("paypal/cancel/slug/<slug:slug>/", views.PaypalFailedView.as_view(), name="cancelled_response_by_slug"),
]