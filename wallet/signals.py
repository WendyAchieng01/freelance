import logging
from decimal import Decimal
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

from core.models import Job
from wallet.models import WalletTransaction, Rate,PayoutLog
from wallet.services.payment_periods import get_or_create_payment_period_for_date
from .models import PayoutLog, WalletTransaction, PaymentBatch
from wallet.services.paystack_bulk_reconcile import reconcile_paystack_batch


logger = logging.getLogger(__name__)


@receiver(m2m_changed, sender=Job.selected_freelancers.through)
def handle_wallet_transactions_on_assignment(sender, instance, action, pk_set, **kwargs):
    job = instance

    if action == "post_add":
        if job.status != "in_progress" and job.selected_freelancers == job.required_freelancers:
            job.status = "in_progress"
            job.save(update_fields=["status"])

        try:
            rate = Rate.objects.latest("effective_from")
        except Rate.DoesNotExist:
            rate = None

        for user_id in pk_set:
            if WalletTransaction.objects.filter(
                job=job,
                user_id=user_id,
                status__in=["in_progress", "pending"]
            ).exists():
                continue

            WalletTransaction.objects.create(
                user_id=user_id,
                transaction_type="job_picked",
                status="in_progress",
                job=job,
                rate=rate,
            )

    elif action in ("post_remove", "post_clear"):
        WalletTransaction.objects.filter(
            job=job,
            user_id__in=pk_set,
            status__in=["in_progress", "pending"],
        ).update(status="cancelled")


@receiver(post_save, sender=Job)
def handle_job_completion(sender, instance, created, **kwargs):
    if created or instance.status != "completed":
        return

    freelancers = instance.selected_freelancers.all()
    if not freelancers.exists():
        return

    # Calculate amounts once (outside loop)
    rate_pct = Decimal('8.00')
    try:
        latest_rate = Rate.objects.latest('effective_from')
        rate_pct = Decimal(latest_rate.rate_amount)
    except Rate.DoesNotExist:
        pass

    total_gross = Decimal(instance.price or '0.00')
    total_fee = (total_gross * (rate_pct / Decimal('100'))
                 ).quantize(Decimal('0.01'))
    net_per_person = ((total_gross - total_fee) /
                      Decimal(instance.required_freelancers)).quantize(Decimal('0.01'))

    period_date = (
        instance.completed_at.date() if hasattr(instance, 'completed_at') and instance.completed_at
        else timezone.now().date()
    )
    period = get_or_create_payment_period_for_date(
        period_date) 

    for user in freelancers:
        # Only create if no payout-like transaction exists yet
        if WalletTransaction.objects.filter(
            job=instance,
            user=user,
            transaction_type='payment_processing',
            status__in=['pending', 'in_progress']
        ).exists():
            continue  # already has a payout record → skip

        WalletTransaction.objects.create(
            user=user,
            job=instance,
            transaction_type="payment_processing",
            status="pending",
            gross_amount=total_gross,
            fee_amount=total_fee,
            amount=net_per_person,
            rate=latest_rate if 'latest_rate' in locals() else None,
            payment_period=period,
        )



@receiver(post_save, sender=PayoutLog)
def payout_log_activity(sender, instance, created, **kwargs):
    logger.debug(
        "[PayoutLog Signal] Fired | id=%s created=%s provider=%s",
        instance.id, created, instance.provider
    )

    # Only Paystack logs
    if instance.provider != "paystack":
        logger.debug("[PayoutLog Signal] Skipped: not paystack")
        return

    if not instance.response_payload or not instance.batch:
        logger.warning(
            "[PayoutLog Signal] Skipped: missing payload or batch | id=%s",
            instance.id
        )
        return

    # Already processed?
    if instance.processed:
        logger.info(
            "[PayoutLog Signal] Already processed | id=%s",
            instance.id
        )
        return

    def _run_reconciliation():
        logger.info(
            "[PayoutLog] Starting reconciliation | log_id=%s batch_id=%s",
            instance.id,
            instance.batch_id,
        )

        try:
            result = reconcile_paystack_batch(
                instance.batch,
                instance.response_payload
            )

            instance.processed = True
            instance.save(update_fields=["processed"])

            logger.info(
                "[PayoutLog] Reconciliation completed | log_id=%s result=%s",
                instance.id,
                result
            )

        except Exception:
            logger.exception(
                "[PayoutLog] Reconciliation FAILED | log_id=%s batch_id=%s",
                instance.id,
                instance.batch_id,
            )

    transaction.on_commit(_run_reconciliation)
    
