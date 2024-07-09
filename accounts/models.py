from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_modified = models.DateTimeField(auto_now=True)
    is_freelancer = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    device_used = models.CharField(max_length=50, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pic/', blank=True, null=True)
    pay_id = models.CharField(max_length=20, choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), default='M-Pesa')
    pay_id_no = models.CharField(max_length=20, default='')
    id_card = models.CharField(max_length=10, blank=True)
    user_type = models.CharField(max_length=20, choices=(('freelancer', 'Freelancer'), ('client', 'Client')), default='freelancer')

    class Meta:
        unique_together = (('user', 'user_type'), )

    def __str__(self):
        return self.user.username
    
def create_profile(sender, instance, created, **kwargs):
    if created:
        user_profile = Profile(user=instance)
        user_profile.save()

post_save.connect(create_profile, sender=User)
