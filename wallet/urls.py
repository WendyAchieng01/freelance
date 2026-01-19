from django.urls import path
from wallet.webhook.paystack import paystack_webhook


app_name ='wallet'

urlpatterns = [
    path("webhooks/paystack/", paystack_webhook),
]
