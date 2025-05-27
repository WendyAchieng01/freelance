# api/invoicemanagement/serializers.py
from rest_framework import serializers
from invoicemgmt.models import Invoice, InvoiceLineItem


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'description', 'quantity', 'rate', 'amount']
        read_only_fields = ['amount']


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True)

    class Meta:
        model = Invoice
        fields = ['id', 'client', 'invoice_number', 'invoice_date',
                    'due_date', 'total_amount', 'status', 'notes', 'line_items']
        read_only_fields = ['invoice_number', 'total_amount']

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items')
        invoice = Invoice.objects.create(**validated_data)
        for line_item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **line_item_data)
        return invoice

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items')
        instance = super().update(instance, validated_data)
        # Simple approach: delete existing line items and recreate
        instance.line_items.all().delete()
        for line_item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=instance, **line_item_data)
        return instance
