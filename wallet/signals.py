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
        if job.status != "in_progress":
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

    for user in freelancers:
        tx, _ = WalletTransaction.objects.get_or_create(
            user=user,
            job=instance,
        )

        tx.transaction_type = "payment_processing"
        tx.status = "pending"

        # Assign payment period (AUTO CREATE)
        period = get_or_create_payment_period_for_date(
            instance.completed_at.date()
            if hasattr(instance, "completed_at") and instance.completed_at
            else timezone.now().date()
        )
        tx.payment_period = period

        tx.save()


def interpret_provider_status(provider, payload):
    """
    Normalize gateway responses into: success | failed | pending
    Adjust this per provider format.
    """
    if not payload:
        return "pending"

    # Example for Paystack-like responses
    status = str(payload.get("status") or payload.get(
        "data", {}).get("status", "")).lower()

    if status in ("success", "successful", "completed","True"):
        return "success"
    if status in ("failed", "error", "reversed"):
        return "failed"

    return "pending"


@receiver(post_save, sender=PayoutLog)
def payout_log_activity(sender, instance, created, **kwargs):
    # We only care about Paystack logs with a response payload and a batch
    if instance.provider != "paystack":
        return

    if not instance.response_payload or not instance.batch:
        return

    # If this log has already been reconciled, skip
    # (Assumes you add something like instance.reconciled = True after success)
    if getattr(instance, "reconciled", False):
        return

    def _run_reconciliation():
        try:
            print(
                f"[PAYOUT LOG] Reconciling batch {instance.batch} "
                f"from log {instance.id}"
            )

            result = reconcile_paystack_batch(
                instance.batch,
                instance.response_payload
            )

            # Mark as reconciled to prevent re-running
            instance.reconciled = True
            instance.save(update_fields=["reconciled"])

            print(f"[PAYOUT LOG] Reconciliation result: {result}")

        except Exception as e:
            # Never crash the save pipeline
            print(f"[PAYOUT LOG] Reconciliation failed: {e}")

    # Run after the DB transaction commits
    transaction.on_commit(_run_reconciliation)
    
