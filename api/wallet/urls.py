from django.urls import path
from .views import WalletTransactionListView, WalletSummaryView

urlpatterns = [
    path('transactions/list/', WalletTransactionListView.as_view(), name='wallet-list-transactions'),
    path('transactions/', WalletTransactionListView.as_view(),name='wallet-transactions'),
    path('summary/', WalletSummaryView.as_view(), name='wallet-summary'),
]
