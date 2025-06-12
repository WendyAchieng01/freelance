from django.urls import path
from . import views

urlpatterns = [
    path('initiate/<slug:slug>/',views.InitiatePaypalPayment.as_view(), name='initiate-by-slug'),
    #path('status/<int:payment_id>/',views.PaymentStatus.as_view(), name='paypal-status'),
    path("success/slug/<str:invoice>/", views.PaypalSuccessView.as_view(), name="successful_response_by_slug"),
    path("cancel/slug/<str:invoice>/", views.PaypalFailedView.as_view(), name="cancelled_response_by_slug"),
]