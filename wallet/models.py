import uuid
from django.db import models
from django.contrib.auth.models import User
from core.models import Job
from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone


def generate_batch_reference():
    return uuid.uuid4().hex



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


class Rate(models.Model):
    """
    Canonical platform fee rate history. Transactions reference a Rate row.
    """
    rate_amount = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Platform fee in percentage")
    effective_from = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.rate_amount}%"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('job_picked', 'Job Picked'),
        ('payment_processing', 'Payment Processing'),
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
    rate = models.ForeignKey(
        Rate, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions',
        help_text="Optional link to the Rate record used when this tx was created"
    )
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPES, null=True, blank=True)
    transaction_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True)
    # Amount fields:
    gross_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Gross amount for the job (before platform fee)")
    fee_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Platform fee amount (gross * rate)")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Net amount payable to freelancer (gross_amount - fee_amount). Kept as 'amount' for compatibility."
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')
    job = models.ForeignKey(Job, on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='wallet_transactions')
    payment_period = models.ForeignKey(
        PaymentPeriod, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions', help_text="Payment period this transaction belongs to"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    extra_data = models.JSONField(default=dict, blank=True)
    batch = models.ForeignKey('PaymentBatch', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='transactions')
    provider_reference = models.CharField(
        max_length=255, blank=True, null=True)

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

    def _get_rate_amount_decimal(self):
        """
        Returns the numeric rate (percentage) used for this transaction.
        Priority:
          1. linked self.rate.rate_amount (if Rate FK is set)
          2. latest Rate in DB
          3. fallback to 8.00%
        """
        if self.rate:
            return Decimal(self.rate.rate_amount)
        try:
            latest = Rate.objects.latest('effective_from')
            return Decimal(latest.rate_amount)
        except Exception:
            return Decimal('8.00')

    def compute_amounts(self):
        """
        Ensure gross_amount, fee_amount, and amount (net) are computed and present.
        - gross_amount: usually from job.price
        - fee_amount: gross_amount * rate/100
        - amount: gross_amount - fee_amount  (kept in 'amount' for compatibility)
        This method is idempotent (won't override already-set values unless they are None).
        """
        # Set gross from job.price if not present
        if not self.gross_amount and self.job and getattr(self.job, "price", None) is not None:
            self.gross_amount = Decimal(self.job.price)

        # Determine rate %
        rate_pct = self._get_rate_amount_decimal()

        # Compute fee_amount if missing
        if self.gross_amount is not None and self.fee_amount is None:
            try:
                self.fee_amount = (Decimal(rate_pct) /
                                   Decimal('100')) * Decimal(self.gross_amount)
            except Exception:
                self.fee_amount = Decimal('0.00')

        # Compute net amount (amount) if missing
        if self.gross_amount is not None and self.fee_amount is not None and self.amount is None:
            try:
                self.amount = Decimal(self.gross_amount) - \
                    Decimal(self.fee_amount)
            except Exception:
                self.amount = Decimal('0.00')

    def save(self, *args, **kwargs):
        # compute amounts using Rate FK if present, otherwise fallback to latest Rate.
        self.compute_amounts()

        # Assign payment period correctly if not already set
        if not self.payment_period:
            # Prefer job assigned_at if available
            tx_date = None
            if self.job and hasattr(self.job, "assigned_at") and self.job.assigned_at:
                tx_date = self.job.assigned_at.date()
            else:
                tx_date = (self.timestamp or timezone.now()).date()

            period = PaymentPeriod.get_period_for_date(tx_date)
            if period:
                self.payment_period = period
            else:
                # fallback: leave null (admin/service should handle creating/assigning periods)
                self.payment_period = None

        super().save(*args, **kwargs)

    @property
    def provider_payout_amount(self):
        """
        Amount gateways should send. This is the net payout (self.amount).
        """
        return self.amount or Decimal('0.00')

    @classmethod
    def pending_completed_jobs(cls):
        """
        Convenience: WalletTransactions attached to Jobs that are completed
        and are still pending payout and not assigned to a batch.
        """
        return cls.objects.filter(
            job__status='completed',
            status='pending',
            batch__isnull=True
        )

    @classmethod
    def completed_jobs_total(cls, user):
        return cls.objects.filter(user=user, status='completed').count()

    @classmethod
    def total_earnings(cls, user):
        """Sum of net earnings from completed jobs (uses `amount`)."""
        transactions = cls.objects.filter(user=user, status='completed')
        total = transactions.aggregate(total=models.Sum('amount'))[
            'total'] or Decimal('0.00')
        return total

    @classmethod
    def total_gross_earnings(cls, user):
        """Sum of gross earnings (before fees) from completed jobs"""
        return cls.objects.filter(user=user, status='completed').aggregate(
            total=models.Sum('gross_amount')
        )['total'] or Decimal('0.00')

    @classmethod
    def earnings_in_period(cls, user, period):
        """Net earnings for a user in a specific payment period (uses `amount`)."""
        transactions = cls.objects.filter(
            user=user, status='completed', payment_period=period)
        return transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @classmethod
    def total_in_period(cls, period):
        """Total net payouts for all freelancers in a given payment period"""
        return cls.objects.filter(status='completed', payment_period=period).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')


class PaymentBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        max_length=100, unique=True, default=generate_batch_reference)
    provider = models.CharField(max_length=20, choices=[(
        'paystack', 'Paystack'), ('paypal', 'PayPal')])
    period = models.ForeignKey(
        PaymentPeriod, on_delete=models.CASCADE, related_name='batches', null=True, blank=True)
    provider_reference = models.CharField(
        max_length=255, blank=True, null=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='payment_batches')
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'), ('processing', 'Processing'),
        ('completed', 'Completed'), ('partial', 'Partial'), ('failed', 'Failed')])
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'period', 'provider')

    def __str__(self):
        return f"{self.reference}"



class PayoutLog(models.Model):
    """
    Audit trail for every gateway call for debugging / reconciliation
    """
    created_at = models.DateTimeField(auto_now_add=True)
    wallet_transaction = models.ForeignKey(
        WalletTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='payout_logs')
    batch = models.ForeignKey(
        PaymentBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    provider = models.CharField(max_length=20)
    endpoint = models.CharField(max_length=255)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PayoutLog {self.provider} {self.endpoint} [{self.id}]"
