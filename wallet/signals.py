from core.models import Job
from wallet.models import WalletTransaction
from decimal import Decimal
from django.db.models.signals import pre_save
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WalletTransaction
from payments.models import PaypalPayments
from payment.models import Payment
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Job)
def create_wallet_transaction_for_job(sender, instance, **kwargs):
    if not instance.pk:
        # It's a new job, do nothing here
        return

    previous = Job.objects.get(pk=instance.pk)

    # Only trigger when freelancer is newly assigned
    if not previous.selected_freelancer and instance.selected_freelancer:
        instance.status = 'in_progress'

        # Prevent duplicate transactions
        if not WalletTransaction.objects.filter(job=instance).exists():
            WalletTransaction.objects.create(
                user=instance.selected_freelancer,
                transaction_type='job_picked',
                status='in_progress',
                job=instance,
                amount=instance.price,
                rate=Decimal('10.00')  # Adjust platform fee as needed
            )


