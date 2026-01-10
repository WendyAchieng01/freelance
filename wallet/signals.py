import logging
from django.db.models import Sum
from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Job
from wallet.models import WalletTransaction, Rate, PaymentBatch, PaymentPeriod

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Job)
def handle_wallet_transaction_on_freelancer_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    previous = Job.objects.get(pk=instance.pk)

    # Newly assigned freelancer → create transaction
    if not previous.selected_freelancer and instance.selected_freelancer:
        instance.status = 'in_progress'

        if not WalletTransaction.objects.filter(job=instance, status__in=['in_progress', 'pending']).exists():
            try:
                rate_obj = Rate.objects.latest('effective_from')
            except Rate.DoesNotExist:
                rate_obj = Decimal('10.00')

            WalletTransaction.objects.create(
                user=instance.selected_freelancer,
                transaction_type='job_picked',
                status='in_progress',
                job=instance,
                rate=rate_obj
            )

    # Freelancer unassigned → cancel latest active transaction
    elif previous.selected_freelancer and not instance.selected_freelancer:
        tx = WalletTransaction.objects.filter(
            job=instance, status__in=['in_progress', 'pending']).last()
        if tx:
            tx.status = 'cancelled'
            tx.save(update_fields=['status'])

    # Freelancer changed → cancel old transaction & create new one
    elif previous.selected_freelancer and instance.selected_freelancer and previous.selected_freelancer != instance.selected_freelancer:
        # Cancel old active tx
        tx = WalletTransaction.objects.filter(
            job=instance, status__in=['in_progress', 'pending']).last()
        if tx:
            tx.status = 'cancelled'
            tx.save(update_fields=['status'])

        # Create new tx
        try:
            rate = Rate.objects.latest('effective_from')
        except Rate.DoesNotExist:
            rate = Decimal('10.00')

        WalletTransaction.objects.create(
            user=instance.selected_freelancer,
            transaction_type='job_picked',
            status='in_progress',
            job=instance,
            rate=rate
        )


@receiver(post_save, sender=Job)
def handle_wallet_transactions_on_job_completion_and_batch(sender, instance, created, **kwargs):
    if created:
        return

    # Only act if job is completed and a freelancer is assigned
    if instance.status == 'completed' and instance.selected_freelancer:

        # Create or get WalletTransaction for this job if none exists
        wallet_tx, created_tx = WalletTransaction.objects.get_or_create(
            user=instance.selected_freelancer,
            job=instance,
            defaults={
                'transaction_type': 'payment_processing',  # new type
                'status': 'pending'  # pending until batch payout is made
            }
        )

        # Ensure transaction_type and status are correct
        wallet_tx.transaction_type = 'payment_processing'
        wallet_tx.status = 'pending'
        wallet_tx.save(update_fields=['transaction_type', 'status'])

        # Create PaymentBatch for this user & period if it doesn't exist
        period = wallet_tx.payment_period
        provider = 'paystack'  # or set dynamically if needed
        batch, created_batch = PaymentBatch.objects.get_or_create(
            period=period,
            provider=provider,
            user=wallet_tx.user,  # required field
            defaults={
                'total_amount': wallet_tx.amount or Decimal('0.00'),
                'status': 'pending'
            }
        )

        # If batch already exists, just update total_amount
        if not created_batch:
            batch.total_amount += wallet_tx.amount or Decimal('0.00')
            batch.save(update_fields=['total_amount'])

        # Link WalletTransaction to batch
        wallet_tx.batch = batch
        wallet_tx.save(update_fields=['batch'])
