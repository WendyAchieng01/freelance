from django.urls import path
from . import views

urlpatterns = [
    path('payment/initiate/<int:job_id>/',views.InitiatePaypalPayment.as_view(), name='initiate-by-id'),
    path('payment/initiate/<slug:slug>/',views.InitiatePaypalPayment.as_view(), name='initiate-by-slug'),
    path('payment/status/<int:payment_id>/',views.PaymentStatus.as_view(), name='paypal-status'),
    path("payment/success/id/<str:invoice>/", views.PaypalSuccessView.as_view(), name="successful_response_by_id"),
    path("payment/success/slug/<str:invoice>/", views.PaypalSuccessView.as_view(), name="successful_response_by_slug"),
    path("payment/cancel/id/<str:invoice>/", views.PaypalFailedView.as_view(), name="cancelled_response_by_id"),
    path("payment/cancel/slug/<str:invoice>/", views.PaypalFailedView.as_view(), name="cancelled_response_by_slug"),
]