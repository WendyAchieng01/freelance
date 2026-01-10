import logging
from decimal import Decimal

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from core.models import Job
from wallet.models import WalletTransaction, Rate, PaymentBatch

logger = logging.getLogger(__name__)


# Handle freelancer assignment / removal (M2M)
@receiver(m2m_changed, sender=Job.selected_freelancers.through)
def handle_wallet_transactions_on_assignment(sender, instance, action, pk_set, **kwargs):
    job = instance

    if action == "post_add":
        # Ensure job is in progress
        if job.status != "in_progress":
            job.status = "in_progress"
            job.save(update_fields=["status"])

        try:
            rate = Rate.objects.latest("effective_from")
        except Rate.DoesNotExist:
            rate = Decimal("10.00")

        for user_id in pk_set:
            # Avoid duplicates
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
        # Cancel active transactions for removed freelancers
        WalletTransaction.objects.filter(
            job=job,
            user_id__in=pk_set,
            status__in=["in_progress", "pending"],
        ).update(status="cancelled")


# Handle job completion & batching (MULTI freelancer)
@receiver(post_save, sender=Job)
def handle_wallet_transactions_on_job_completion(sender, instance, created, **kwargs):
    if created:
        return

    if instance.status != "completed":
        return

    freelancers = instance.selected_freelancers.all()
    if not freelancers.exists():
        return

    for user in freelancers:
        wallet_tx, _ = WalletTransaction.objects.get_or_create(
            user=user,
            job=instance,
            defaults={
                "transaction_type": "payment_processing",
                "status": "pending",
            },
        )

        wallet_tx.transaction_type = "payment_processing"
        wallet_tx.status = "pending"
        wallet_tx.save(update_fields=["transaction_type", "status"])

        period = wallet_tx.payment_period
        provider = "paystack"  # or dynamic

        batch, created_batch = PaymentBatch.objects.get_or_create(
            period=period,
            provider=provider,
            user=user,
            defaults={
                "total_amount": wallet_tx.amount or Decimal("0.00"),
                "status": "pending",
            },
        )

        if not created_batch:
            batch.total_amount += wallet_tx.amount or Decimal("0.00")
            batch.save(update_fields=["total_amount"])

        wallet_tx.batch = batch
        wallet_tx.save(update_fields=["batch"])
