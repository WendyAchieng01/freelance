from .models import Job, Chat
from accounts.models import Profile
from .models import Job
from django.db.models.signals import post_save,pre_save
from django.dispatch import receiver
from core.models import Job,Chat


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