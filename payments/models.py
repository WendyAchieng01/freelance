from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PaypalPayments(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    job = models.ForeignKey('core.Job', on_delete=models.CASCADE)
    invoice = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    email = models.EmailField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    # Stores additional data like response_id
    extra_data = models.JSONField(default=dict)

    def __str__(self):
        return f"Payment {self.invoice} - {self.status}"
