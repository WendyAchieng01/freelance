from django.utils import timezone
from django.db import transaction
from decimal import Decimal, ROUND_DOWN
from rest_framework import serializers

MAX_FILE_SIZE_MB = 3


def validate_file(file, allowed_extensions):
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise serializers.ValidationError(
            f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}")
    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise serializers.ValidationError(
            f"File size must be under {MAX_FILE_SIZE_MB}MB")


def split_job_payment(job, period=None):
    from wallet.models import WalletTransaction
    """
    Split a Job's payment among all selected freelancers.
    Creates per-freelancer `payment_processing` WalletTransactions.

    Args:
        job (Job): the completed job instance
        period (PaymentPeriod, optional): pre-determined payment period. If None, auto-create.
    """
    freelancers = list(job.selected_freelancers.all())
    count = len(freelancers)
    if count == 0:
        return

    # Prevent duplicate splits
    already_split = WalletTransaction.objects.filter(
        job=job,
        transaction_type="payment_processing",
        extra_data__split=True
    ).exists()
    if already_split:
        return

    # Compute full job fee & net
    temp_tx = WalletTransaction(job=job, gross_amount=job.price)
    temp_tx.compute_amounts()
    gross_total = Decimal(temp_tx.gross_amount or 0)
    fee_total = Decimal(temp_tx.fee_amount or 0)
    net_total = gross_total - fee_total

    if net_total <= 0:
        return

    # Split net among freelancers
    split_amount = (net_total / count).quantize(Decimal("0.01"),
                                                rounding=ROUND_DOWN)
    remainder = net_total - (split_amount * count)

    # Determine payment period
    if period is None:
        from wallet.services.payment_periods import get_or_create_payment_period_for_date
        period = get_or_create_payment_period_for_date(
            job.completed_at.date() if hasattr(job, "completed_at") and job.completed_at
            else timezone.now().date()
        )

    with transaction.atomic():
        for index, user in enumerate(freelancers):
            payout = split_amount
            if index == 0:
                payout += remainder  # absorb rounding

            tx, created = WalletTransaction.objects.get_or_create(
                user=user,
                job=job,
                transaction_type="payment_processing",
                defaults={
                    "gross_amount": gross_total,    
                    "fee_amount": fee_total,  
                    "amount": payout,            
                    "status": "pending",
                    "completed": False,
                    "payment_period": period,
                    "extra_data": {"split": True, "freelancers": count},
                },
            )

            if not created:
                tx.gross_amount = gross_total
                tx.fee_amount = fee_total
                tx.amount = payout
                tx.status = "pending"
                tx.completed = False
                tx.payment_period = period
                tx.extra_data["split"] = True
                tx.extra_data["freelancers"] = count
                tx.save()
