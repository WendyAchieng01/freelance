from django.db import models
from django.contrib.auth.models import User
from core.models import Job
from decimal import Decimal
from django.db.models import Sum, F


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('job_picked', 'Job Picked'),
        ('payment_received', 'Payment Received'),
    )
    PAYMENT_TYPES = (
        ('paystack', 'Paystack'),
        ('paypal', 'PayPal'),
    )
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Platform fee rate in %")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    job = models.OneToOneField(Job, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']
        verbose_name_plural = "Wallet Transactions"

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.transaction_id or 'N/A'}"

    def net_earning(self):
        """Calculate earnings after platform fee"""
        if self.amount:
            fee = self.amount * (self.rate / Decimal(100))
            return self.amount - fee
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        # Fetch current rate
        if self.rate is None:
            try:
                from wallet.models import Rate
                self.rate = Rate.objects.latest('effective_from').rate_amount
            except Rate.DoesNotExist:
                self.rate = Decimal('10.00')  # default

        # Calculate net amount (price - rate%)
        if self.job and self.amount is None:
            gross = self.job.price
            fee = (self.rate / Decimal('100')) * gross
            self.amount = gross - fee

        super().save(*args, **kwargs)


    @classmethod
    def completed_jobs_total(cls, user):
        return cls.objects.filter(user=user, status='completed').count()

    @classmethod
    def total_earnings(cls, user):
        """Sum of net earnings from completed jobs"""
        transactions = cls.objects.filter(user=user, status='completed')
        total = sum(t.net_earning() for t in transactions)
        return total


class Rate(models.Model):
    rate_amount = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Platform fee in percentage")
    effective_from = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rate_amount}%"
