from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WalletTransaction
from core.models import JobAssignment
from payments.models import PaypalPayments
from payment.models import Payment
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=JobAssignment)
def create_pending_transaction_on_job_pick(sender, instance, created, **kwargs):
    logger.debug(
        f"JobAssignment post_save: created={created}, instance={instance}")
    if created:
        try:
            user = instance.freelancer.user
            job = instance.job
            logger.debug(
                f"Checking for existing job_picked transaction for user={user.username}, job={job.id}")
            if not WalletTransaction.objects.filter(
                user=user,
                job=job,
                transaction_type='job_picked'
            ).exists():
                logger.debug(f"Creating job_picked transaction")
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='job_picked',
                    status='pending',
                    job=job,
                    extra_data={'assignment_id': instance.id}
                )
                logger.info(
                    f"Created job_picked transaction for user={user.username}, job={job.id}")
            else:
                logger.debug("job_picked transaction already exists")
        except AttributeError as e:
            logger.error(f"AttributeError in job_picked signal: {e}")
        except Exception as e:
            logger.error(f"Error creating job_picked transaction: {e}")


@receiver(post_save, sender=Payment)
def handle_paystack_payment(sender, instance, created, **kwargs):
    logger.debug(f"Payment post_save: created={created}, ref={instance.ref}")
    try:
        assignment = JobAssignment.objects.filter(job=instance.job).first()
        if not assignment:
            logger.debug(
                f"No JobAssignment for job={instance.job.id}, skipping Paystack payment handling")
            return

        user = assignment.freelancer.user
        status = 'completed' if instance.verified else 'pending'
        if created:
            logger.debug(
                f"Checking for job_picked transaction for user={user.username}, job={instance.job.id}")
            wallet_tx = WalletTransaction.objects.filter(
                user=user,
                job=instance.job,
                transaction_type='job_picked'
            ).first()
            if wallet_tx:
                logger.debug(
                    f"Updating job_picked to payment_received: id={wallet_tx.id}")
                wallet_tx.transaction_type = 'payment_received'
                wallet_tx.payment_type = 'paystack'
                wallet_tx.transaction_id = instance.ref
                wallet_tx.amount = instance.amount
                wallet_tx.status = status
                wallet_tx.extra_data.update({
                    'payment_id': instance.id,
                    'original_assignment_id': wallet_tx.extra_data.get('assignment_id')
                })
                wallet_tx.save()
                logger.info(
                    f"Updated to payment_received for user={user.username}, ref={instance.ref}")
            else:
                logger.debug(
                    f"No job_picked transaction, creating payment_received")
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='payment_received',
                    payment_type='paystack',
                    transaction_id=instance.ref,
                    amount=instance.amount,
                    status=status,
                    job=instance.job,
                    extra_data={'payment_id': instance.id}
                )
                logger.info(
                    f"Created payment_received transaction for user={user.username}, ref={instance.ref}")
        else:
            wallet_tx = WalletTransaction.objects.filter(
                transaction_id=instance.ref,
                payment_type='paystack'
            ).first()
            if wallet_tx:
                logger.debug(
                    f"Updating existing payment_received: id={wallet_tx.id}")
                wallet_tx.status = status
                wallet_tx.amount = instance.amount
                wallet_tx.extra_data.update({'payment_id': instance.id})
                wallet_tx.save()
    except Exception as e:
        logger.error(f"Error handling Paystack payment: {e}")


@receiver(post_save, sender=PaypalPayments)
def handle_paypal_payment(sender, instance, created, **kwargs):
    logger.debug(
        f"PaypalPayments post_save: created={created}, invoice={instance.invoice}")
    try:
        assignment = JobAssignment.objects.filter(job=instance.job).first()
        if not assignment:
            logger.debug(
                f"No JobAssignment for job={instance.job.id}, skipping PayPal payment handling")
            return

        user = assignment.freelancer.user
        if created:
            logger.debug(
                f"Checking for job_picked transaction for user={user.username}, job={instance.job.id}")
            wallet_tx = WalletTransaction.objects.filter(
                user=user,
                job=instance.job,
                transaction_type='job_picked'
            ).first()
            if wallet_tx:
                logger.debug(
                    f"Updating job_picked to payment_received: id={wallet_tx.id}")
                wallet_tx.transaction_type = 'payment_received'
                wallet_tx.payment_type = 'paypal'
                wallet_tx.transaction_id = instance.invoice
                wallet_tx.amount = instance.amount
                wallet_tx.status = instance.status
                wallet_tx.extra_data.update({
                    'payment_id': instance.id,
                    'original_assignment_id': wallet_tx.extra_data.get('assignment_id')
                })
                wallet_tx.save()
                logger.info(
                    f"Updated to payment_received for user={user.username}, invoice={instance.invoice}")
            else:
                logger.debug(
                    f"No job_picked transaction, creating payment_received")
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='payment_received',
                    payment_type='paypal',
                    transaction_id=instance.invoice,
                    amount=instance.amount,
                    status=instance.status,
                    job=instance.job,
                    extra_data={'payment_id': instance.id}
                )
                logger.info(
                    f"Created payment_received transaction for user={user.username}, invoice={instance.invoice}")
        else:
            wallet_tx = WalletTransaction.objects.filter(
                transaction_id=instance.invoice,
                payment_type='paypal'
            ).first()
            if wallet_tx:
                logger.debug(
                    f"Updating existing payment_received: id={wallet_tx.id}")
                wallet_tx.status = instance.status
                wallet_tx.amount = instance.amount
                wallet_tx.extra_data.update({'payment_id': instance.id})
                wallet_tx.save()
    except Exception as e:
        logger.error(f"Error handling PayPal payment: {e}")
