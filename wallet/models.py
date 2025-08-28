from django.db import models
from django.contrib.auth.models import User
from core.models import Job
from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone


class PaymentPeriod(models.Model):
    name = models.CharField(
        max_length=100, help_text="Name of the payment period, e.g. 'August 2025 - Week 1'")
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-start_date']
        unique_together = ('start_date', 'end_date')
        verbose_name = "Payment Period"
        verbose_name_plural = "Payment Periods"

    def __str__(self):
        return f"{self.name} ({self.start_date} → {self.end_date})"

    def includes(self, date):
        """Check if a given date falls within this period"""
        return self.start_date <= date <= self.end_date

    @classmethod
    def get_period_for_date(cls, date):
        """Find the payment period covering a given date"""
        return cls.objects.filter(start_date__lte=date, end_date__gte=date).first()


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

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(
        max_length=20, choices=TRANSACTION_TYPES)
    rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00, help_text="Platform fee rate in %")
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPES, null=True, blank=True)
    transaction_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='wallet_transactions')
    payment_period = models.ForeignKey(
        'PaymentPeriod',on_delete=models.SET_NULL,null=True,blank=True,
        related_name='transactions',help_text="Payment period this transaction belongs to"
    )
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
                self.rate = Decimal('8.00')

        # Calculate net amount (price - rate%)
        if self.job and self.amount is None:
            gross = self.job.price
            fee = (self.rate / Decimal('100')) * gross
            self.amount = gross - fee

        # Assign payment period if not already set
        if not self.payment_period:
            tx_date = (self.timestamp or timezone.now()).date()
            period = PaymentPeriod.get_period_for_date(tx_date)

            if period:
                # only current/future periods allowed
                if period.start_date >= timezone.now().date():
                    self.payment_period = period
                else:
                    raise ValueError(
                        "Cannot assign transaction to a past payment period. Please create a valid current/future period.")

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

    @classmethod
    def total_gross_earnings(cls, user):
        """Sum of gross earnings (before fees) from completed jobs"""
        return cls.objects.filter(user=user, status='completed').aggregate(
            total=models.Sum('job__price')
        )['total'] or Decimal('0.00')

    @classmethod
    def earnings_in_period(cls, user, period):
        """Net earnings for a user in a specific payment period"""
        transactions = cls.objects.filter(
            user=user, status='completed', payment_period=period)
        return sum(t.net_earning() for t in transactions)

    @classmethod
    def total_in_period(cls, period):
        """Total payouts for all freelancers in a given payment period"""
        return cls.objects.filter(status='completed', payment_period=period).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')



class Rate(models.Model):
    rate_amount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Platform fee in percentage")
    effective_from = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rate_amount}%"
