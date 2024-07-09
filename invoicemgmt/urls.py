from django.urls import include, path
from . import views

app_name = 'invoicemgmt'

urlpatterns = [
    path("", views.invoice_index, name="invoice_index"), 
    path("list/", views.invoice_list, name="invoice_list"),
    path('invoices/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),
    path('delete/<int:invoice_id>/', views.delete_invoice, name='delete_invoice'),
    path('invoices/<int:invoice_id>/pdf/', views.generate_invoice_pdf_view, name='generate_invoice_pdf'),
]