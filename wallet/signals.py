from core.models import Job
from wallet.models import WalletTransaction, Rate
from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging

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
                rate = Rate.objects.latest('effective_from').rate_amount
            except Rate.DoesNotExist:
                rate = Decimal('10.00')

            WalletTransaction.objects.create(
                user=instance.selected_freelancer,
                transaction_type='job_picked',
                status='in_progress',
                job=instance,
                rate=rate
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
            rate = Rate.objects.latest('effective_from').rate_amount
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
def update_wallet_transaction_on_completion(sender, instance, created, **kwargs):
    if created:
        return

    # When job is completed, update active transaction
    if instance.status == 'completed':
        tx = WalletTransaction.objects.filter(job=instance).last()
        if tx and tx.status != 'completed':
            tx.status = 'completed'
            tx.completed = True
            tx.save(update_fields=['status', 'completed'])
