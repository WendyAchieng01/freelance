from django.db.models import Sum, Q
from decimal import Decimal
from core.models import Job
from wallet.models import WalletTransaction


def get_wallet_stats(user):
    stats = {}
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'user_type', None)

    if role == 'client':
        jobs = Job.objects.filter(client=profile)
        total_jobs = jobs.count()

        # Only consider jobs that were paid
        paid_jobs = jobs.filter(payment_verified=True)
        total_spent = paid_jobs.aggregate(total=Sum('price'))[
            'total'] or Decimal('0.00')

        stats.update({
            "user_type": "client",
            "total_jobs_posted": total_jobs,
            "total_amount_spent": total_spent,
        })

    elif role == 'freelancer':
        # Only consider transactions linked to jobs where this user was selected
        transactions = WalletTransaction.objects.filter(
            user=user,
            job__selected_freelancers=user
        ).select_related('job')

        total_picked_jobs = transactions.filter(
            transaction_type='job_picked'
        ).count()

        in_progress_jobs = Job.objects.filter(
            selected_freelancers=user,
            status='in_progress'
        )

        expected_earnings = in_progress_jobs.aggregate(
            total=Sum('price')
        )['total'] or Decimal('0.00')

        completed = transactions.filter(status='completed')
        pending = transactions.filter(status__in=['pending', 'in_progress'])
        failed = transactions.filter(status='failed')
        cancelled = transactions.filter(status='cancelled')

        total_earned = sum(t.net_earning() for t in completed)
        pending_earnings = sum(t.net_earning() for t in pending)

        stats.update({
            "user_type": "freelancer",
            "total_jobs_picked": total_picked_jobs,
            "in_progress_jobs": in_progress_jobs.count(),
            "expected_earnings": expected_earnings,
            "total_earned": total_earned,
            "pending_earnings": pending_earnings,
            "failed_transactions": failed.count(),
            "cancelled_transactions": cancelled.count(),
        })

    return stats
