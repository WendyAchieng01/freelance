from django.db import models
from django.contrib.auth.models import User
from core.models import Job


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
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPES, default=None)
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPES, null=True, blank=True)
    transaction_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    job = models.ForeignKey(
        Job, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
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
