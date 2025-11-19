# analytics/api.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from accounts.models import Profile, Skill
from core.models import Job
from payment.models import Payment
from wallet.models import WalletTransaction

User = get_user_model()


class AnalyticsDataAPI(APIView):
    def get(self, request):
        now = timezone.now()
        months = []
        user_growth = []
        job_growth = []
        revenue_growth = []

        for i in range(11, -1, -1):
            date = now.date().replace(day=1) - relativedelta(months=i)
            months.append(date.strftime("%b %Y"))
            start = date
            end = date + relativedelta(months=1)

            user_growth.append(User.objects.filter(
                date_joined__gte=start, date_joined__lt=end).count())
            job_growth.append(Job.objects.filter(
                posted_date__gte=start, posted_date__lt=end).count())
            rev = Payment.objects.filter(date_created__gte=start, date_created__lt=end, verified=True)\
                .aggregate(s=Sum('amount'))['s'] or 0
            revenue_growth.append(float(rev))

        total_users = User.objects.count()
        total_jobs = Job.objects.count()
        open_jobs = Job.objects.filter(status='open').count()
        in_progress = Job.objects.filter(status='in_progress').count()
        completed_jobs = Job.objects.filter(status='completed').count()
        total_revenue = float(Payment.objects.filter(
            verified=True).aggregate(s=Sum('amount'))['s'] or 0)

        top_skills = list(Skill.objects.annotate(c=Count('required_skills'))
                            .filter(c__gt=0).order_by('-c')[:10].values('name', 'c'))

        return Response({
            'months': months,
            'user_growth': user_growth,
            'job_growth': job_growth,
            'revenue_growth': revenue_growth,
            'total_users': total_users,
            'total_jobs': total_jobs,
            'open_jobs': open_jobs,
            'in_progress_jobs': in_progress,
            'completed_jobs': completed_jobs,
            'total_revenue': total_revenue,
            'top_skills': top_skills,
        })
