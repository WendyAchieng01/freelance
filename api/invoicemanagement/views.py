# api/invoicemanagement/views.py
from rest_framework import generics, permissions
from rest_framework.views import APIView
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from invoicemgmt.models import Invoice
from invoicemgmt.invoice_pdf import generate_invoice_pdf
from .serializers import InvoiceSerializer


class IsStaffUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class InvoiceListCreateView(generics.ListCreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsStaffUser]


class InvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsStaffUser]


class InvoicePDFView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        pdf = generate_invoice_pdf(invoice)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
