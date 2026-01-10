from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.models import Profile, Skill, Language
from core.models import Job, JobCategory
from payment.models import Payment
from payments.models import PaypalPayments
from wallet.models import WalletTransaction
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

User = get_user_model()


class AnalyticsSerializer(serializers.Serializer):
    # Basic stats
    total_users = serializers.IntegerField()
    total_freelancers = serializers.IntegerField()
    total_clients = serializers.IntegerField()
    total_jobs = serializers.IntegerField()
    open_jobs = serializers.IntegerField()
    in_progress_jobs = serializers.IntegerField()
    completed_jobs = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    total_payouts = serializers.FloatField()
    platform_profit = serializers.FloatField()
    avg_responses_per_job = serializers.FloatField()

    # Chart data
    months = serializers.ListField(child=serializers.CharField())
    user_growth = serializers.ListField(child=serializers.IntegerField())
    job_growth = serializers.ListField(child=serializers.IntegerField())
    revenue_growth = serializers.ListField(child=serializers.FloatField())
    profit_growth = serializers.ListField(child=serializers.FloatField())

    # Job status data
    job_status_labels = serializers.ListField(child=serializers.CharField())
    job_status_data = serializers.ListField(child=serializers.IntegerField())

    # Top skills
    top_skills = serializers.ListField(child=serializers.DictField())

    # Radar chart data
    radar_labels = serializers.ListField(child=serializers.CharField())
    radar_data = serializers.ListField(child=serializers.FloatField())

    # Geographic Distribution
    geographic_labels = serializers.ListField(child=serializers.CharField())
    geographic_data = serializers.ListField(child=serializers.IntegerField())

    # Payment Methods
    payment_methods_labels = serializers.ListField(
        child=serializers.CharField())
    payment_methods_data = serializers.ListField(
        child=serializers.FloatField())

    # Top Categories
    top_categories_labels = serializers.ListField(
        child=serializers.CharField())
    top_categories_data = serializers.ListField(
        child=serializers.IntegerField())

    # Most In-Demand Skills (for radar chart)
    top_skills_labels = serializers.ListField(child=serializers.CharField())
    top_skills_data = serializers.ListField(child=serializers.IntegerField())
