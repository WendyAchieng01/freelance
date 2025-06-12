from rest_framework import serializers
from invoicemgmt.models import Invoice, InvoiceLineItem


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'description', 'quantity', 'rate', 'amount']
        read_only_fields = ['amount']


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True)
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date',
            'total_amount', 'status', 'notes', 'line_items', 'user_type'
        ]
        read_only_fields = ['invoice_number',
                            'total_amount', 'user_type', 'status']

    def get_user_type(self, obj):
        return getattr(obj.client.profile, 'user_type', 'unknown')

    def validate(self, data):
        # Prevent edits if already paid
        if self.instance and self.instance.status == 'paid':
            raise serializers.ValidationError(
                "Paid invoices cannot be edited.")
        return data

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        # no duplication of client/status
        invoice = Invoice.objects.create(**validated_data)
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **item_data)
        return invoice

    def update(self, instance, validated_data):
        if instance.status == 'paid':
            raise serializers.ValidationError(
                "Paid invoices cannot be updated.")

        line_items_data = validated_data.pop('line_items', None)
        instance = super().update(instance, validated_data)

        if line_items_data is not None:
            instance.line_items.all().delete()
            for item_data in line_items_data:
                InvoiceLineItem.objects.create(invoice=instance, **item_data)

        return instance
