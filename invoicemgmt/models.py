from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.db import models, IntegrityError, transaction
from django.utils.text import slugify
import uuid


def generate_dummy_invoice_number():
    return f"DUMMY-{get_random_string(length=8)}"

class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='line_items', default=None, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.description)
            slug = base_slug
            counter = 1

            while InvoiceLineItem.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # fallback to uuid if base_slug is empty
            self.slug = slug or str(uuid.uuid4())

        super().save(*args, **kwargs)


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    client = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.PositiveIntegerField(
        unique=True, null=True, blank=True)
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def __str__(self):
        return f"Invoice #{self.invoice_number}"

    def get_total_amount(self):
        total = sum(item.amount for item in self.line_items.all())
        return total

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new and not self.invoice_number:
            last_invoice = Invoice.objects.order_by('invoice_number').last()
            self.invoice_number = (
                last_invoice.invoice_number + 1) if last_invoice else 1

        if not self.slug:
            base_slug = slugify(
                f"invoice-{self.invoice_number or uuid.uuid4().hex[:6]}")
            unique_slug = base_slug
            num = 1
            while Invoice.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug

        super().save(*args, **kwargs)

        if is_new:
            self.total_amount = self.get_total_amount()
            super().save(update_fields=['total_amount'])

