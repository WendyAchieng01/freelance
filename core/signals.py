from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Job
from core.models import Chat


@receiver(post_save, sender=Job)
def create_chat_after_payment(sender, instance, created, **kwargs):
    if instance.payment_verified and not hasattr(instance, 'chat'):
        Chat.objects.create(job=instance, client=instance.client)


@receiver(post_save, sender=Job)
def assign_freelancer_to_chat(sender, instance, **kwargs):
    if instance.selected_freelancer and hasattr(instance, 'chat'):
        chat = instance.chat
        if chat.freelancer != instance.selected_freelancer.profile:
            chat.freelancer = instance.selected_freelancer.profile
            chat.save()
