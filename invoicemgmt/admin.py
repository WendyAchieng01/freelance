from django.contrib import admin
from .models import Invoice, InvoiceLineItem



class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    fields = ('description', 'quantity', 'rate', 'amount')
    readonly_fields = ('amount',)

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'client',
        'invoice_date',
        'due_date',
        'status',
        'total_amount',
        'created_at',
        'updated_at'
    )
    list_filter = ('status', 'invoice_date', 'due_date')
    search_fields = ('invoice_number', 'client__username', 'notes')
    ordering = ('-invoice_number',)
    readonly_fields = ('created_at', 'updated_at', 'total_amount')
    inlines = [InvoiceLineItemInline]

    fieldsets = (
        ("Invoice Details", {
            'fields': (
                'client',
                'invoice_number',
                'invoice_date',
                'due_date',
                'status',
                'notes',
                'total_amount',
                'created_at',
                'updated_at',
            )
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Ensures invoice number and total amount are properly set.
        """
        if not obj.invoice_number:
            last_invoice = Invoice.objects.order_by('-invoice_number').first()
            obj.invoice_number = (
                last_invoice.invoice_number + 1) if last_invoice else 1
        super().save_model(request, obj, form, change)
