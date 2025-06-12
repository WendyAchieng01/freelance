from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from invoicemgmt.models import Invoice
from .serializers import InvoiceSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from invoicemgmt.invoice_pdf import generate_invoice_pdf
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import IsAuthenticated
import traceback


class IsInvoiceOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.client == request.user


class InvoiceDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        try:
            invoice = Invoice.objects.select_related('client__profile') \
                                     .prefetch_related('line_items') \
                                     .get(id=invoice_id)

            if invoice.client != request.user:
                return Response(
                    {"error": "You are not authorized to access this invoice."},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                pdf_data = generate_invoice_pdf(invoice)
                response = HttpResponse(
                    pdf_data, content_type='application/pdf')
                filename = f"Invoice_{invoice.invoice_number or invoice.id}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            except Exception as e:
                return Response(
                    {
                        "error": "PDF generation failed.",
                        "details": str(e),
                        "trace": traceback.format_exc()
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except ObjectDoesNotExist:
            return Response(
                {"error": f"Invoice with ID {invoice_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    "error": "Unexpected server error.",
                    "details": str(e),
                    "trace": traceback.format_exc()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsInvoiceOwner]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['invoice_number', 'notes', 'line_items__description']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount', 'status']
    ordering = ['-invoice_date']

    def get_queryset(self):
        return Invoice.objects.filter(client=self.request.user).prefetch_related('line_items')

    def perform_create(self, serializer):
        serializer.save(client=self.request.user, status='draft')


    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == 'paid':
            return Response(
                {"error": "Paid invoices cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()
        return Response({"message": "Invoice deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
