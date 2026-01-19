from wallet.services.payout_intent_service import PayoutIntentService
from wallet.models import WalletTransaction, Rate, PaymentPeriod
from core.models import Job
from django.db.models.signals import pre_save
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import receiver
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save, pre_save

from core.models import Job, Chat, Profile, Response, Message
from wallet.models import Rate, WalletTransaction, Rate, PaymentPeriod


# Reviewed responses logic
@receiver(m2m_changed, sender=Job.reviewed_responses.through)
def validate_and_update_reviewed_responses(sender, instance, action, pk_set, **kwargs):
    """
    Ensure only Responses linked to this Job are added to reviewed_responses.
    Automatically set status to 'under_review' for valid entries.
    """
    if action == 'pre_add':
        invalid_response_ids = Response.objects.filter(
            pk__in=pk_set
        ).exclude(job=instance).values_list('id', flat=True)

        if invalid_response_ids:
            raise ValidationError(
                f"Responses {list(invalid_response_ids)} do not belong to job '{instance.title}'."
            )

    if action == 'post_add':
        valid_responses = Response.objects.filter(pk__in=pk_set, job=instance)
        for response in valid_responses:
            if response.status not in ['accepted', 'rejected']:
                response.status = 'under_review'
                response.marked_for_review = True
                response.save()


@receiver(m2m_changed, sender=Job.selected_freelancers.through)
def handle_selected_freelancers(sender, instance, action, pk_set, **kwargs):
    job = instance

    # ── Skip when pk_set is None (happens on .clear() / bulk clear) ──
    if pk_set is None:
        if action == "post_clear":
            # After full clear: deactivate ALL chats for this job
            Chat.objects.filter(job=job).update(active=False)

            # Clear assigned_at if no freelancers left (should be true after clear)
            if not job.selected_freelancers.exists():
                job.assigned_at = None
                job.save(update_fields=["assigned_at"])

        # For pre_clear we usually do nothing
        return

    # ── Normal cases with actual pk_set ──

    if action == "post_add":
        # Set assigned_at when at least one freelancer exists
        if job.selected_freelancers.exists():
            job.assigned_at = job.assigned_at or timezone.now() 
            job.save(update_fields=["assigned_at"])

        for user_id in pk_set:
            try:
                freelancer_profile = Profile.objects.get(user_id=user_id)
            except Profile.DoesNotExist:
                continue

            chat, created = Chat.objects.get_or_create(
                job=job,
                client=job.client,
                freelancer=freelancer_profile,
                defaults={'active': job.payment_verified},
            )

            if created:
                send_initial_chat_message(job, job.client, freelancer_profile)

    elif action == "post_remove":
        # Deactivate chats only for the removed freelancers
        profiles = Profile.objects.filter(user_id__in=pk_set)
        Chat.objects.filter(
            job=job,
            freelancer__in=profiles
        ).update(active=False)

        # If no freelancers remain after removal
        if not job.selected_freelancers.exists():
            job.assigned_at = None
            job.save(update_fields=["assigned_at"])

    # post_clear is already handled above when pk_set is None


# Activate chats when payment becomes verified
@receiver(post_save, sender=Job)
def activate_chats_on_payment(sender, instance, created, **kwargs):
    if instance.payment_verified:
        Chat.objects.filter(job=instance).update(active=True)


# First chat message helper
def send_initial_chat_message(job, client_profile, freelancer_profile):
    chat, _ = Chat.objects.get_or_create(
        job=job,
        client=client_profile,
        freelancer=freelancer_profile,
        defaults={'active': True},
    )

    # Get latest rate
    try:
        rate_obj = Rate.objects.latest('effective_from')
        rate_pct = Decimal(rate_obj.rate_amount)
    except Rate.DoesNotExist:
        rate_pct = Decimal('10.00')
    except Exception:
        rate_pct = Decimal('10.00')

    # Gross, Fee, Net
    gross = Decimal(job.price) if getattr(
        job, 'price', None) else Decimal('0.00')
    fee = (rate_pct / Decimal('100')) * gross
    net_amount = gross - fee

    message_text = (
        f"👋 Hi {freelancer_profile.user.first_name or freelancer_profile.user.username},\n\n"
        f"I’m {client_profile.user.first_name or client_profile.user.username}, "
        f"and I’ve just accepted you for the job **'{job.title}'**.\n\n"
        f"Platform fee rate: {rate_pct}%\n"
        f"Project rate (after platform fee): Kes {net_amount:.2f}\n"
        f"Expected deadline: "
        f"{job.deadline_date.strftime('%b %d, %Y') if job.deadline_date else 'Not specified'}\n\n"
        f"Welcome aboard! Let’s get started — feel free to ask anything.\n\n"
        f"— {client_profile.user.first_name or client_profile.user.username}"
    )

    Message.objects.create(
        chat=chat,
        sender=client_profile.user,
        content=message_text
    )


@receiver(post_save, sender=Job)
def trigger_payout_intents_on_completion(sender, instance, created, **kwargs):
    if created:
        return

    # Only act when job is completed


@receiver(post_save, sender=Job)
def trigger_payout_intents_on_completion(sender, instance, created, **kwargs):
    if created:
        return

    # Only act when job is completed
    if instance.status != "completed":
        return

    PayoutIntentService.create_for_completed_job(instance)
    if instance.status != "completed":
        return

    PayoutIntentService.create_for_completed_job(instance)
