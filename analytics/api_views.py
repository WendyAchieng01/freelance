import json
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.authentication import SessionAuthentication
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count, Avg, Q
from collections import Counter

from django.contrib.auth import get_user_model
from accounts.models import Profile, Skill, Language
from core.models import Job, JobCategory
from payment.models import Payment
from payments.models import PaypalPayments
from wallet.models import WalletTransaction

from .serializers import AnalyticsSerializer

User = get_user_model()


@method_decorator(staff_member_required, name='dispatch')
class AnalyticsAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated,IsAdminUser]

    def get(self, request):
        # Verify user is staff
        if not request.user.is_staff:
            return Response({"detail": "Permission denied."}, status=403)

        now = timezone.now()

        # === LAST 12 MONTHS DATA ===
        months = []
        user_growth = []
        job_growth = []
        revenue_growth = []

        for i in range(11, -1, -1):
            date = (now.date().replace(day=1) - relativedelta(months=i))
            months.append(date.strftime("%b %Y"))
            start = date
            end = date + relativedelta(months=1)

            user_growth.append(User.objects.filter(
                date_joined__gte=start, date_joined__lt=end).count())
            job_growth.append(Job.objects.filter(
                posted_date__gte=start, posted_date__lt=end).count())

            rev = Payment.objects.filter(date_created__gte=start, date_created__lt=end, verified=True)\
                .aggregate(s=Sum('amount'))['s'] or Decimal('0')
            revenue_growth.append(float(rev))

        # === BASIC STATS ===
        total_users = User.objects.count()
        total_freelancers = Profile.objects.filter(
            user_type='freelancer').count()
        total_clients = Profile.objects.filter(user_type='client').count()

        total_jobs = Job.objects.count()
        open_jobs = Job.objects.filter(status='open').count()
        in_progress = Job.objects.filter(status='in_progress').count()
        completed_jobs = Job.objects.filter(status='completed').count()

        total_revenue = Payment.objects.filter(verified=True).aggregate(
            s=Sum('amount'))['s'] or Decimal('0')
        total_payouts = WalletTransaction.objects.filter(
            status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        platform_profit = total_revenue - total_payouts

        avg_responses = Job.objects.annotate(num_apps=Count(
            'responses')).aggregate(avg=Avg('num_apps'))['avg'] or 0

        # === TOP SKILLS ===
        top_skills = list(Skill.objects.annotate(count=Count('required_skills'))
                          .filter(count__gt=0).order_by('-count')[:10]
                          .values('name', 'count'))

        # === RADAR CHART DATA ===
        radar_labels = ['Users', 'Jobs', 'Revenue',
                        'Hires', 'Profit', 'Activity']
        radar_data = [
            min(total_users // 10, 100),
            min(total_jobs // 5, 100),
            min(float(total_revenue) // 1000, 100),
            min(in_progress * 3, 100),
            min(float(platform_profit) // 500, 100),
            min((in_progress + completed_jobs) /
                max(total_jobs or 1, 1) * 100, 100)
        ]

        # GEOGRAPHIC DISTRIBUTION
        geographic_data = self.get_geographic_distribution()
        geographic_labels = list(geographic_data.keys())
        geographic_values = list(geographic_data.values())

        # PAYMENT METHODS
        payment_methods_data = self.get_payment_methods_distribution()
        payment_methods_labels = list(payment_methods_data.keys())
        payment_methods_values = list(payment_methods_data.values())

        # TOP CATEGORIES
        top_categories_data = self.get_top_categories()
        top_categories_labels = list(top_categories_data.keys())
        top_categories_values = list(top_categories_data.values())

        # MOST IN-DEMAND SKILLS (for radar chart)
        top_skills_data = self.get_most_in_demand_skills()
        top_skills_labels = list(top_skills_data.keys())
        top_skills_values = list(top_skills_data.values())

        data = {
            # Basic stats
            'total_users': total_users,
            'total_freelancers': total_freelancers,
            'total_clients': total_clients,
            'total_jobs': total_jobs,
            'open_jobs': open_jobs,
            'in_progress_jobs': in_progress,
            'completed_jobs': completed_jobs,
            'total_revenue': float(total_revenue),
            'total_payouts': float(total_payouts),
            'platform_profit': float(platform_profit),
            'avg_responses_per_job': round(avg_responses, 1),

            # Chart data
            'months': months,
            'user_growth': user_growth,
            'job_growth': job_growth,
            'revenue_growth': revenue_growth,

            # Job status
            'job_status_labels': ['Open', 'In Progress', 'Completed'],
            'job_status_data': [open_jobs, in_progress, completed_jobs],

            # Top skills
            'top_skills': top_skills,

            # Radar chart
            'radar_labels': radar_labels,
            'radar_data': radar_data,

            'geographic_labels': geographic_labels,
            'geographic_data': geographic_values,
            'payment_methods_labels': payment_methods_labels,
            'payment_methods_data': payment_methods_values,
            'top_categories_labels': top_categories_labels,
            'top_categories_data': top_categories_values,
            'top_skills_labels': top_skills_labels,
            'top_skills_data': top_skills_values,
        }

        serializer = AnalyticsSerializer(data)
        return Response(serializer.data)

    def get_geographic_distribution(self):
        """Get user distribution by location"""
        # Get non-empty locations and count users
        locations = Profile.objects.exclude(
            Q(location__isnull=True) | Q(location='')
        ).values('location').annotate(
            user_count=Count('id')
        ).order_by('-user_count')[:8]  # Top 8 locations

        geographic_data = {}
        for item in locations:
            location_name = item['location'] or 'Unknown'
            geographic_data[location_name] = item['user_count']

        return geographic_data

    def get_payment_methods_distribution(self):
        """Get payment methods distribution"""
        payment_data = {}

        # Paystack payments (verified)
        paystack_total = Payment.objects.filter(verified=True).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        payment_data['Paystack'] = float(paystack_total)

        # PayPal payments (completed)
        paypal_total = PaypalPayments.objects.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        payment_data['PayPal'] = float(paypal_total)

        # If you have other payment methods, add them here
        # payment_data['Other'] = float(other_total)

        return payment_data

    def get_top_categories(self):
        """Get top job categories by job count"""
        categories = JobCategory.objects.annotate(
            job_count=Count('jobs')
        ).filter(job_count__gt=0).order_by('-job_count')[:10]

        category_data = {}
        for category in categories:
            category_data[category.name] = category.job_count

        return category_data

    def get_most_in_demand_skills(self):
        """Get most in-demand skills for radar chart"""
        # Get skills ordered by demand (jobs requiring them)
        skills = Skill.objects.annotate(
            demand_count=Count('required_skills')
        ).filter(demand_count__gt=0).order_by('-demand_count')[:10]

        skills_data = {}
        for skill in skills:
            skills_data[skill.get_name_display()] = skill.demand_count

        return skills_data
