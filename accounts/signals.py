from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, FreelancerProfile, ClientProfile
from .utils import is_disposable_email 


@receiver(post_save, sender=User)
def update_email_verified(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        email = instance.email
        profile = instance.profile

        if instance.is_active and not is_disposable_email(email):
            profile.email_verified = True
        else:
            profile.email_verified = False

        profile.save()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):

    profile, _ = Profile.objects.get_or_create(user=instance)

    if instance.profile.user_type == 'freelancer':
        FreelancerProfile.objects.get_or_create(profile=profile)
    elif instance.profile.user_type == 'client':
        ClientProfile.objects.get_or_create(profile=profile)
