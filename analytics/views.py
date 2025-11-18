import json
from datetime import date
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F, DurationField, ExpressionWrapper
from django.views.generic import TemplateView
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from django.db.models.functions import TruncMonth, TruncDay, ExtractWeek
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import DateTimeField

from payment.models import Payment
from invoicemgmt.models import Invoice
from payments.models import PaypalPayments
from wallet.models import WalletTransaction
from core.models import Job, JobCategory, Response, Chat, Review
from accounts.models import Profile, Skill, PortfolioProject, FreelancerProfile, ClientProfile

User = get_user_model()


def is_staff_user(user):
    return user.is_staff


@user_passes_test(is_staff_user)
def analytics_dashboard(request):
    # ─── BASIC TOTALS ─────────────────────────────────────────────────────
    total_users = get_user_model().objects.count()
    total_freelancers = Profile.objects.filter(user_type='freelancer').count()
    total_clients = Profile.objects.filter(user_type='client').count()

    total_jobs = Job.objects.count()
    open_jobs = Job.objects.filter(status='open').count()
    in_progress_jobs = Job.objects.filter(status='in_progress').count()
    completed_jobs = Job.objects.filter(status='completed').count()

    total_responses = Response.objects.count()
    avg_responses_per_job = Job.objects.annotate(resp_count=Count('responses')) \
        .aggregate(Avg('resp_count'))['resp_count__avg'] or 0.0

    total_chats = Chat.objects.count()
    total_portfolio_projects = PortfolioProject.objects.count()
    total_reviews = Review.objects.count()
    average_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0.0
    average_rating = round(average_rating, 2)

    # ─── FINANCIAL TOTALS ─────────────────────────────────────────────────
    verified_payments = Payment.objects.filter(verified=True)
    total_revenue = verified_payments.aggregate(total=Sum('amount'))[
        'total'] or Decimal('0.00')

    completed_transactions = WalletTransaction.objects.select_related(
        'job').filter(status='completed')
    total_payouts = completed_transactions.aggregate(
        total=Sum('amount'))['total'] or Decimal('0.00')

    platform_fees = Decimal('0.00')
    for t in completed_transactions:
        if t.job and t.amount is not None:
            platform_fees += t.job.price - t.amount

    # ─── USER ENGAGEMENT METRICS ──────────────────────────────────────────
    thirty_days_ago = timezone.now() - timedelta(days=30)

    active_users_chat = User.objects.filter(
        Q(message__timestamp__gte=thirty_days_ago) |
        Q(profile__client_chats__created_at__gte=thirty_days_ago) |
        Q(profile__freelancer_chats__created_at__gte=thirty_days_ago)
    ).distinct().count()

    active_users_jobs = User.objects.filter(
        Q(profile__jobs__posted_date__gte=thirty_days_ago) |
        Q(response__submitted_at__gte=thirty_days_ago)
    ).distinct().count()

    active_users_payments = User.objects.filter(
        Q(payment__date_created__gte=thirty_days_ago) |
        Q(paypalpayments__isnull=False)
    ).distinct().count()

    active_users_total = User.objects.filter(
        Q(message__timestamp__gte=thirty_days_ago) |
        Q(profile__client_chats__created_at__gte=thirty_days_ago) |
        Q(profile__freelancer_chats__created_at__gte=thirty_days_ago) |
        Q(profile__jobs__posted_date__gte=thirty_days_ago) |
        Q(response__submitted_at__gte=thirty_days_ago) |
        Q(payment__date_created__gte=thirty_days_ago) |
        Q(paypalpayments__isnull=False) |
        Q(date_joined__gte=thirty_days_ago)
    ).distinct().count()

    # Response rates
    jobs_with_responses = Job.objects.filter(
        responses__isnull=False).distinct().count()
    response_rate = (jobs_with_responses / total_jobs *
                     100) if total_jobs > 0 else 0

    # Application conversion rate
    total_applications = Response.objects.count()
    accepted_applications = Response.objects.filter(status='accepted').count()
    conversion_rate = (accepted_applications /
                       total_applications * 100) if total_applications > 0 else 0

    # ─── GEOGRAPHIC DISTRIBUTION ──────────────────────────────────────────
    location_data = Profile.objects.exclude(location='').exclude(location__isnull=True).values('location').annotate(
        count=Count('id')
    ).order_by('-count')[:15]

    geographic_labels = [item['location']
                         for item in location_data] if location_data else ['No Data']
    geographic_data = [item['count']
                       for item in location_data] if location_data else [0]

    # ─── FREELANCER PERFORMANCE ANALYTICS ────────────────────────────────
    top_freelancers = FreelancerProfile.objects.annotate(
        completed_jobs_count=Count(
            'profile__user__selected_jobs',
            filter=Q(profile__user__selected_jobs__status='completed')
        ),
        total_earnings=Sum(
            'profile__user__wallet_transactions__amount',
            filter=Q(profile__user__wallet_transactions__status='completed')
        ),
        avg_rating=Avg('profile__user__reviews_received__rating')
    ).filter(completed_jobs_count__gt=0).order_by('-total_earnings')[:10]

    freelancer_performance_data = {
        'labels': [f.profile.user.username for f in top_freelancers],
        'completed_jobs': [f.completed_jobs_count or 0 for f in top_freelancers],
        'earnings': [float(f.total_earnings or 0) for f in top_freelancers],
        'ratings': [float(f.avg_rating or 0) for f in top_freelancers]
    }

    # Freelancer skill distribution
    popular_skills = Skill.objects.annotate(
        freelancer_count=Count('freelancerprofile', distinct=True)
    ).filter(freelancer_count__gt=0).order_by('-freelancer_count')[:10]

    skill_distribution_labels = [skill.get_name_display()
                                 for skill in popular_skills]
    skill_distribution_data = [
        skill.freelancer_count for skill in popular_skills]

    # ─── CLIENT SPENDING PATTERNS ────────────────────────────────────────
    top_clients = ClientProfile.objects.annotate(
        total_spent=Sum('profile__jobs__payment__amount', filter=Q(
            profile__jobs__payment__verified=True)),
        jobs_posted=Count('profile__jobs'),
        avg_job_budget=Avg('profile__jobs__price')
    ).filter(total_spent__isnull=False).order_by('-total_spent')[:10]

    client_spending_data = {
        'labels': [c.profile.user.username for c in top_clients],
        'total_spent': [float(c.total_spent or 0) for c in top_clients],
        'jobs_posted': [c.jobs_posted for c in top_clients],
        'avg_budget': [float(c.avg_job_budget or 0) for c in top_clients]
    }

    # Client industry distribution
    industry_spending = ClientProfile.objects.exclude(industry='').exclude(industry__isnull=True).values('industry').annotate(
        total_spent=Sum('profile__jobs__payment__amount', filter=Q(
            profile__jobs__payment__verified=True)),
        client_count=Count('id')
    ).order_by('-total_spent')

    industry_labels = [item['industry']
                       for item in industry_spending] if industry_spending else ['No Data']
    industry_spending_data = [float(item['total_spent'] or 0)
                              for item in industry_spending] if industry_spending else [0]

    # ─── PAYMENT METHOD PREFERENCES ──────────────────────────────────────
    paystack_payments = Payment.objects.filter(verified=True).count()
    paypal_payments = PaypalPayments.objects.filter(status='completed').count()
    total_verified_payments = paystack_payments + paypal_payments

    payment_method_data = {
        'labels': ['Paystack', 'PayPal'],
        'data': [
            paystack_payments,
            paypal_payments
        ],
        'percentages': [
            (paystack_payments / total_verified_payments *
             100) if total_verified_payments > 0 else 0,
            (paypal_payments / total_verified_payments *
             100) if total_verified_payments > 0 else 0
        ]
    }

    # ─── PLATFORM EFFICIENCY METRICS ─────────────────────────────────────
    completed_jobs_count = Job.objects.filter(status='completed').count()
    total_jobs_with_freelancers = Job.objects.filter(
        selected_freelancer__isnull=False).count()
    completion_rate = (completed_jobs_count / total_jobs_with_freelancers *
                       100) if total_jobs_with_freelancers > 0 else 0

    # Time-to-hire analysis
    jobs_with_hire_data = Job.objects.filter(
        selected_freelancer__isnull=False,
        posted_date__isnull=False,
        assigned_at__isnull=False
    )

    if jobs_with_hire_data.exists():
        total_days = 0
        count = 0
        for job in jobs_with_hire_data:
            if job.posted_date and job.assigned_at:
                time_diff = job.assigned_at - job.posted_date
                total_days += time_diff.total_seconds() / (24 * 3600)
                count += 1
        avg_time_to_hire_days = total_days / count if count > 0 else 0
    else:
        avg_time_to_hire_days = 0

    # Job fulfillment time
    completed_jobs_with_dates = Job.objects.filter(
        status='completed',
        posted_date__isnull=False
    )

    if completed_jobs_with_dates.exists():
        total_fulfillment_days = 0
        count = 0
        for job in completed_jobs_with_dates:
            if job.posted_date:
                completion_date = timezone.now()
                time_diff = completion_date - job.posted_date
                total_fulfillment_days += time_diff.total_seconds() / (24 * 3600)
                count += 1
        avg_fulfillment_days = total_fulfillment_days / count if count > 0 else 0
    else:
        avg_fulfillment_days = 0

    # ─── RADAR CHART DATA - Platform Health Overview ─────────────────────
    radar_labels = ['User Growth', 'Job Posts', 'Response Rate',
                    'Completion Rate', 'Revenue', 'User Satisfaction']

    # Scale values for radar chart (0-100 scale)
    user_growth_score = min(
        (active_users_total / total_users * 100) if total_users > 0 else 0, 100)
    job_posts_score = min((total_jobs / max(total_users, 1)) * 10, 100)
    response_rate_score = response_rate
    completion_rate_score = completion_rate
    revenue_score = min(float(total_revenue) / 100,
                        100) if total_revenue else 0
    satisfaction_score = average_rating * 20

    radar_data = [
        user_growth_score,
        job_posts_score,
        response_rate_score,
        completion_rate_score,
        revenue_score,
        satisfaction_score
    ]

    # ─── LAST 12 MONTHS SERIES ───────────────────────────────────────────
    end_date = timezone.now()
    start_date = end_date - relativedelta(months=11)

    labels = []
    current = (timezone.now().date().replace(day=1) - relativedelta(months=11))
    for i in range(12):
        labels.append(current.strftime('%b %Y'))
        current += relativedelta(months=1)

    def monthly_dict(qs, date_field):
        return {item['month'].strftime('%Y-%m'): item['count']
                for item in qs}

    def monthly_sum_dict(qs, date_field):
        return {item['month'].strftime('%Y-%m'): float(item['total'] or 0)
                for item in qs}

    # User growth
    user_monthly = User.objects.filter(date_joined__gte=start_date)\
        .annotate(month=TruncMonth('date_joined'))\
        .values('month').annotate(count=Count('id')).order_by('month')
    user_dict = monthly_dict(user_monthly, 'date_joined')
    user_growth_data = [user_dict.get(
        f"{(timezone.now().date().replace(day=1) - relativedelta(months=(11-i))).strftime('%Y-%m')}", 0) for i in range(12)]

    # Job posted growth
    job_monthly = Job.objects.filter(posted_date__gte=start_date)\
        .annotate(month=TruncMonth('posted_date'))\
        .values('month').annotate(count=Count('id')).order_by('month')
    job_dict = monthly_dict(job_monthly, 'posted_date')
    job_growth_data = [job_dict.get(
        f"{(timezone.now().date().replace(day=1) - relativedelta(months=(11-i))).strftime('%Y-%m')}", 0) for i in range(12)]

    # Revenue growth
    revenue_monthly = verified_payments.filter(date_created__gte=start_date)\
        .annotate(month=TruncMonth('date_created'))\
        .values('month').annotate(total=Sum('amount')).order_by('month')
    revenue_dict = monthly_sum_dict(revenue_monthly, 'date_created')
    revenue_growth_data = [revenue_dict.get(
        f"{(timezone.now().date().replace(day=1) - relativedelta(months=(11-i))).strftime('%Y-%m')}", 0.0) for i in range(12)]

    # Payouts growth
    payout_monthly = completed_transactions.filter(timestamp__gte=start_date)\
        .annotate(month=TruncMonth('timestamp'))\
        .values('month').annotate(total=Sum('amount')).order_by('month')
    payout_dict = monthly_sum_dict(payout_monthly, 'timestamp')
    payout_growth_data = [payout_dict.get(
        f"{(timezone.now().date().replace(day=1) - relativedelta(months=(11-i))).strftime('%Y-%m')}", 0.0) for i in range(12)]

    # ─── TOP CATEGORIES & SKILLS ─────────────────────────────────────────
    top_categories = JobCategory.objects.annotate(count=Count('jobs'))\
        .order_by('-count')[:10]
    top_categories_labels = [cat.name for cat in top_categories]
    top_categories_data = [cat.count for cat in top_categories]

    top_skills = Skill.objects.annotate(count=Count('required_skills'))\
        .filter(count__gt=0).order_by('-count')[:10]
    top_skills_labels = [skill.get_name_display() for skill in top_skills]
    top_skills_data = [skill.count for skill in top_skills]

    # ─── JOB STATUS PIE CHART ────────────────────────────────────────────
    status_data = Job.objects.values('status').annotate(count=Count('id'))
    status_dict = {item['status']: item['count'] for item in status_data}
    job_status_labels = ['Open', 'In Progress', 'Completed']
    job_status_data = [
        status_dict.get('open', 0),
        status_dict.get('in_progress', 0),
        status_dict.get('completed', 0),
    ]

    # ─── CONTEXT ─────────────────────────────────────────────────────────
    context = {
        # Totals (cards)
        'total_users': total_users,
        'total_freelancers': total_freelancers,
        'total_clients': total_clients,
        'total_jobs': total_jobs,
        'open_jobs': open_jobs,
        'in_progress_jobs': in_progress_jobs,
        'completed_jobs': completed_jobs,
        'total_responses': total_responses,
        'avg_responses_per_job': round(avg_responses_per_job, 2),
        'total_revenue': float(total_revenue),
        'total_payouts': float(total_payouts),
        'platform_fees': float(platform_fees),
        'total_reviews': total_reviews,
        'average_rating': average_rating,

        # User Engagement Metrics
        'active_users_total': active_users_total,
        'active_users_chat': active_users_chat,
        'active_users_jobs': active_users_jobs,
        'active_users_payments': active_users_payments,
        'response_rate': round(response_rate, 2),
        'conversion_rate': round(conversion_rate, 2),

        # Platform Efficiency
        'completion_rate': round(completion_rate, 2),
        'avg_time_to_hire_days': round(avg_time_to_hire_days, 1),
        'avg_fulfillment_days': round(avg_fulfillment_days, 1),

        # Chart data (Chart.js ready) - ALL REQUIRED DATA
        'chart_labels_json': json.dumps(labels),

        'user_growth_data_json': json.dumps(user_growth_data),
        'job_growth_data_json': json.dumps(job_growth_data),
        'revenue_growth_data_json': json.dumps(revenue_growth_data),
        'payout_growth_data_json': json.dumps(payout_growth_data),

        'top_categories_labels_json': json.dumps(top_categories_labels),
        'top_categories_data_json': json.dumps(top_categories_data),

        'top_skills_labels_json': json.dumps(top_skills_labels),
        'top_skills_data_json': json.dumps(top_skills_data),

        'job_status_labels_json': json.dumps(job_status_labels),
        'job_status_data_json': json.dumps(job_status_data),

        # New Analytics Data - ALL REQUIRED
        'geographic_labels_json': json.dumps(geographic_labels),
        'geographic_data_json': json.dumps(geographic_data),

        'freelancer_performance_data_json': json.dumps(freelancer_performance_data),
        'skill_distribution_labels_json': json.dumps(skill_distribution_labels),
        'skill_distribution_data_json': json.dumps(skill_distribution_data),

        'client_spending_data_json': json.dumps(client_spending_data),
        'industry_labels_json': json.dumps(industry_labels),
        'industry_spending_data_json': json.dumps(industry_spending_data),

        'payment_method_data_json': json.dumps(payment_method_data),

        'radar_labels_json': json.dumps(radar_labels),
        'radar_data_json': json.dumps(radar_data),

        'title': 'Enhanced Platform Analytics Dashboard',
    }

    # Debug: Print context keys to console
    print("Context keys being passed:", list(context.keys()))

    return render(request, 'admin/analytics_dashboard.html', context)
