# api/invoicemanagement/urls.py
from django.urls import path
from .views import InvoiceListCreateView, InvoiceDetailView, InvoicePDFView

urlpatterns = [
    path('invoices/', InvoiceListCreateView.as_view(), name='invoice-list-create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/<int:invoice_id>/pdf/',
            InvoicePDFView.as_view(), name='invoice-pdf'),
]
