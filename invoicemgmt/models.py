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
    invoice_number = models.CharField(max_length=20, unique=True)
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
            if not self.invoice_number:
                # Use a database sequence to generate a unique invoice number
                with transaction.atomic():
                    try:
                        # Get the next value from the sequence
                        from django.db import connection
                        cursor = connection.cursor()
                        cursor.execute("SELECT nextval('invoice_number_sequence')")
                        next_value = cursor.fetchone()[0]
                        self.invoice_number = str(next_value).zfill(6)  # Format as string with leading zeros if necessary
                    except IntegrityError:
                        # Handle the case where the sequence is not initialized
                        # You may need to create the sequence in your database manually
                        # For PostgreSQL, you can create a sequence using:
                        # CREATE SEQUENCE invoice_number_sequence START 1;
                        self.invoice_number = "000001"
            super().save(*args, **kwargs)

            # Calculate the total amount before saving the instance
            self.total_amount = self.get_total_amount()
            super().save(*args, **kwargs)