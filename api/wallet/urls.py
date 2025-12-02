from django.urls import path
from .views import WalletTransactionListView, WalletSummaryView
from .wbhooks import paypal_webhook,paystack_webhook

urlpatterns = [
    path('transactions/', WalletTransactionListView.as_view(),name='wallet-transactions'),
    path('summary/', WalletSummaryView.as_view(), name='wallet-summary'),
    path("wbhk/paystack/", paystack_webhook, name="paystack-webhook"),
    path("wbhk/paypal/", paypal_webhook, name="paypal-webhook"),
]
