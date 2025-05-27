from django.urls import path
from .views import WalletListView

urlpatterns = [
    path('', WalletListView.as_view(), name='wallet-list'),
]
