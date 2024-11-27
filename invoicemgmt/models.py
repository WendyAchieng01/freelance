from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.db import models, IntegrityError, transaction


def generate_dummy_invoice_number():
    return f"DUMMY-{get_random_string(length=8)}"

class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='line_items', default=None, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.PositiveIntegerField(unique=True, null=True, blank=True)  # Use a numeric field
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice #{self.invoice_number}"

    def get_total_amount(self):
        total = sum(item.amount for item in self.line_items.all())
        return total

    def save(self, *args, **kwargs):
        # Generate invoice_number if not already set
        if not self.invoice_number:
            last_invoice = Invoice.objects.order_by('invoice_number').last()
            self.invoice_number = (last_invoice.invoice_number + 1) if last_invoice else 1

        # Save the instance first to ensure it has a primary key
        super().save(*args, **kwargs)

        # Calculate total_amount using related objects
        self.total_amount = self.get_total_amount()

        # Save again to update the total_amount
        super().save(*args, **kwargs)

