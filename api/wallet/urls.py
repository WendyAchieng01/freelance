from django.urls import path
from .views import WalletTransactionListView, WalletSummaryView

urlpatterns = [
    path('transactions/', WalletTransactionListView.as_view(),name='wallet-transactions'),
    path('summary/', WalletSummaryView.as_view(), name='wallet-summary'),
]
