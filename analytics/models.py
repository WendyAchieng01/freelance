from django.db import models
from django.utils import timezone
from django.core.cache import cache
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import F
from decimal import Decimal


class DailyAnalytics(models.Model):
    date = models.DateField(unique=True)
    new_users = models.IntegerField(default=0)
    new_freelancers = models.IntegerField(default=0)
    new_clients = models.IntegerField(default=0)
    new_jobs = models.IntegerField(default=0)
    new_applications = models.IntegerField(default=0)
    new_hires = models.IntegerField(default=0)
    total_users = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payouts = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    platform_fees = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=['date'])]
        ordering = ['-date']

    @classmethod
    def update_today(cls):
        today = timezone.now().date()
        obj, _ = cls.objects.get_or_create(date=today)

        from django.contrib.auth import get_user_model
        from accounts.models import Profile
        from core.models import Job, Response
        from payment.models import Payment
        from wallet.models import WalletTransaction

        User = get_user_model()

        # New users today
        obj.new_users = User.objects.filter(date_joined__date=today).count()
        obj.new_freelancers = Profile.objects.filter(
            user_type='freelancer', user__date_joined__date=today).count()
        obj.new_clients = Profile.objects.filter(
            user_type='client', user__date_joined__date=today).count()

        # Jobs & Applications
        obj.new_jobs = Job.objects.filter(posted_date__date=today).count()
        obj.new_applications = Response.objects.filter(
            submitted_at__date=today).count()

        # New hires today (when assigned_at is today)
        obj.new_hires = Job.objects.filter(
            assigned_at__date=today,
            selected_freelancer__isnull=False
        ).count()

        # Revenue today
        payments_today = Payment.objects.filter(
            date_created__date=today, verified=True)
        obj.revenue = payments_today.aggregate(t=models.Sum('amount'))[
            't'] or Decimal('0')

        # Payouts today
        payouts_today = WalletTransaction.objects.filter(
            timestamp__date=today, status='completed')
        obj.payouts = payouts_today.aggregate(t=models.Sum('amount'))[
            't'] or Decimal('0')

        # Platform fees
        obj.platform_fees = obj.revenue - obj.payouts

        obj.save()
