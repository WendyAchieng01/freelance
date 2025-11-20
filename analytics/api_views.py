import json
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count, Avg

from django.contrib.auth import get_user_model
from accounts.models import Profile, Skill
from core.models import Job
from payment.models import Payment
from wallet.models import WalletTransaction

from .serializers import AnalyticsSerializer

User = get_user_model()


@method_decorator(staff_member_required, name='dispatch')
class AnalyticsAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

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
        }

        serializer = AnalyticsSerializer(data)
        return Response(serializer.data)
