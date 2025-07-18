from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save,pre_save
from django.dispatch import receiver
from core.models import Job,Chat,Profile,Response,Message
from django.core.exceptions import ValidationError

@receiver(pre_save, sender=Job)
def cache_old_job_values(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Job.objects.get(pk=instance.pk)
            instance._old_selected_freelancer = old_instance.selected_freelancer
            instance._old_payment_verified = old_instance.payment_verified
        except Job.DoesNotExist:
            instance._old_selected_freelancer = None
            instance._old_payment_verified = False
    else:
        instance._old_selected_freelancer = None
        instance._old_payment_verified = False


@receiver(post_save, sender=Job)
def update_response_status_on_job_change(sender, instance, **kwargs):
    responses = instance.responses.all()
    for response in responses:
        response.save()


@receiver(m2m_changed, sender=Job.reviewed_responses.through)
def validate_and_update_reviewed_responses(sender, instance, action, pk_set, **kwargs):
    """
    Ensure only Responses linked to this Job are added to reviewed_responses.
    Automatically set status to 'under_review' for valid entries.
    """
    if action == 'pre_add':
        invalid_response_ids = Response.objects.filter(
            pk__in=pk_set).exclude(job=instance).values_list('id', flat=True)
        if invalid_response_ids:
            raise ValidationError(
                f"Responses {list(invalid_response_ids)} do not belong to job '{instance.title}'.")

    if action == 'post_add':
        valid_responses = Response.objects.filter(pk__in=pk_set, job=instance)
        for response in valid_responses:
            if response.status not in ['accepted', 'rejected']:
                response.status = 'under_review'
                response.marked_for_review = True
                response.save()


@receiver(post_save, sender=Job)
def manage_chat_on_job_update(sender, instance, created, **kwargs):
    job = instance
    old_freelancer = getattr(job, "_old_selected_freelancer", None)
    old_payment = getattr(job, "_old_payment_verified", False)
    new_freelancer = job.selected_freelancer
    new_payment = job.payment_verified

    # If a freelancer is assigned or changed
    if new_freelancer:
        try:
            freelancer_profile = Profile.objects.get(user=new_freelancer)
        except Profile.DoesNotExist:
            return  # Or log warning

        # Always ensure a chat exists (even if inactive initially)
        chat, chat_created = Chat.objects.get_or_create(
            job=job,
            client=job.client,
            freelancer=freelancer_profile,
            # Set active=True only if already paid
            defaults={'active': new_payment},
        )

        # If freelancer changed, deactivate chat with old freelancer
        if old_freelancer and old_freelancer != new_freelancer:
            try:
                old_profile = Profile.objects.get(user=old_freelancer)
                Chat.objects.filter(
                    job=job, freelancer=old_profile).update(active=False)
            except Profile.DoesNotExist:
                pass

        # If chat exists but payment just became verified, activate chat
        if new_payment and not chat.active:
            chat.active = True
            chat.save()

    # If freelancer was removed
    elif old_freelancer and not new_freelancer:
        try:
            old_profile = Profile.objects.get(user=old_freelancer)
            Chat.objects.filter(
                job=job, freelancer=old_profile).update(active=False)
        except Profile.DoesNotExist:
            pass

