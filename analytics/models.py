from datetime import date
from decimal import Decimal
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.core.cache import cache
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model



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


class GeographicAnalytics(models.Model):
    """Track user distribution by location"""
    date = models.DateField()
    location = models.CharField(max_length=200)
    user_count = models.IntegerField(default=0)
    freelancer_count = models.IntegerField(default=0)
    client_count = models.IntegerField(default=0)
    job_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('date', 'location')
        indexes = [models.Index(fields=['date', 'location'])]
        ordering = ['-date', 'location']

    @classmethod
    def update_geographic_data(cls, date=None):
        if date is None:
            date = timezone.now().date()

        from accounts.models import Profile
        from core.models import Job

        # Get all unique locations from profiles
        locations = Profile.objects.exclude(location='').values_list(
            'location', flat=True).distinct()

        for location in locations:
            if location:  # Skip empty locations
                obj, _ = cls.objects.get_or_create(
                    date=date, location=location)

                # Count users by location
                profiles_in_location = Profile.objects.filter(
                    location=location)
                obj.user_count = profiles_in_location.count()
                obj.freelancer_count = profiles_in_location.filter(
                    user_type='freelancer').count()
                obj.client_count = profiles_in_location.filter(
                    user_type='client').count()

                # Count jobs by client location
                client_profiles = profiles_in_location.filter(
                    user_type='client')
                client_users = [profile.user for profile in client_profiles]
                obj.job_count = Job.objects.filter(
                    client__user__in=client_users).count()

                obj.save()


class PaymentMethodAnalytics(models.Model):
    """Track payment method usage"""
    date = models.DateField()
    # 'paystack', 'paypal', etc.
    payment_method = models.CharField(max_length=50)
    transaction_count = models.IntegerField(default=0)
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    successful_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('date', 'payment_method')
        indexes = [models.Index(fields=['date', 'payment_method'])]
        ordering = ['-date', 'payment_method']

    @classmethod
    def update_payment_methods(cls, date=None):
        if date is None:
            date = timezone.now().date()

        from payment.models import Payment
        from payments.models import PaypalPayments

        # Paystack payments
        paystack_payments = Payment.objects.filter(date_created__date=date)
        paystack_obj, _ = cls.objects.get_or_create(
            date=date,
            payment_method='paystack'
        )
        paystack_obj.transaction_count = paystack_payments.count()
        paystack_obj.total_amount = sum(p.amount for p in paystack_payments)
        paystack_obj.successful_count = paystack_payments.filter(
            verified=True).count()
        paystack_obj.save()

        # PayPal payments
        paypal_payments = PaypalPayments.objects.filter(
            models.Q(extra_data__has_key='created_date') |
            # Fallback - you might need to add a date field
            models.Q(id__isnull=False)
        )
        # Filter by date if possible, or use creation logic
        paypal_obj, _ = cls.objects.get_or_create(
            date=date,
            payment_method='paypal'
        )
        paypal_obj.transaction_count = paypal_payments.count()
        paypal_obj.total_amount = sum(p.amount for p in paypal_payments)
        paypal_obj.successful_count = paypal_payments.filter(
            status='completed').count()
        paypal_obj.save()


class CategoryAnalytics(models.Model):
    """Track job categories performance"""
    date = models.DateField()
    category = models.ForeignKey('core.JobCategory', on_delete=models.CASCADE)
    job_count = models.IntegerField(default=0)
    application_count = models.IntegerField(default=0)
    completion_count = models.IntegerField(default=0)
    avg_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('date', 'category')
        indexes = [models.Index(fields=['date', 'category'])]
        ordering = ['-date', '-job_count']

    @classmethod
    def update_categories(cls, date=None):
        if date is None:
            date = timezone.now().date()

        from core.models import JobCategory, Job, Response

        categories = JobCategory.objects.all()

        for category in categories:
            obj, _ = cls.objects.get_or_create(date=date, category=category)

            # Jobs in this category
            category_jobs = Job.objects.filter(
                category=category, posted_date__date=date)
            obj.job_count = category_jobs.count()

            # Applications for these jobs
            obj.application_count = Response.objects.filter(
                job__in=category_jobs,
                submitted_at__date=date
            ).count()

            # Completed jobs
            obj.completion_count = category_jobs.filter(
                status='completed').count()

            # Average price
            if category_jobs.exists():
                obj.avg_price = category_jobs.aggregate(
                    avg=models.Avg('price'))['avg']

            obj.save()


class SkillsAnalytics(models.Model):
    """Track skills demand and supply"""
    date = models.DateField()
    skill = models.ForeignKey('accounts.Skill', on_delete=models.CASCADE)
    demand_count = models.IntegerField(default=0)  # Jobs requiring this skill
    supply_count = models.IntegerField(
        default=0)  # Freelancers with this skill
    avg_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('date', 'skill')
        indexes = [models.Index(fields=['date', 'skill'])]
        ordering = ['-date', '-demand_count']

    @classmethod
    def update_skills(cls, date=None):
        if date is None:
            date = timezone.now().date()

        from accounts.models import Skill, FreelancerProfile
        from core.models import Job

        skills = Skill.objects.all()

        for skill in skills:
            obj, _ = cls.objects.get_or_create(date=date, skill=skill)

            # Demand: Jobs requiring this skill
            obj.demand_count = Job.objects.filter(
                skills_required=skill,
                posted_date__date=date
            ).count()

            # Supply: Freelancers with this skill
            obj.supply_count = FreelancerProfile.objects.filter(
                skills=skill,
                profile__user__date_joined__date=date
            ).count()

            # Average hourly rate for this skill
            freelancers_with_skill = FreelancerProfile.objects.filter(
                skills=skill)
            if freelancers_with_skill.exists():
                obj.avg_hourly_rate = freelancers_with_skill.aggregate(
                    avg=models.Avg('hourly_rate')
                )['avg']

            obj.save()


class ComprehensiveAnalytics(models.Model):
    """Main analytics model that aggregates all data for the dashboard"""
    date = models.DateField(unique=True)

    # Update all analytics in one method
    @classmethod
    def update_all_analytics(cls, date=None):
        if date is None:
            date = timezone.now().date()

        # Update existing DailyAnalytics
        from analytics.models import DailyAnalytics
        DailyAnalytics.update_today()

        # Update new analytics models
        GeographicAnalytics.update_geographic_data(date)
        PaymentMethodAnalytics.update_payment_methods(date)
        CategoryAnalytics.update_categories(date)
        SkillsAnalytics.update_skills(date)

        # Get or create comprehensive record
        obj, created = cls.objects.get_or_create(date=date)
        obj.save()
