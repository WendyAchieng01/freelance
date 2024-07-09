from django.db import models
from django.contrib.auth.models import User

from accounts.models import Profile


# Create your models here.
class Job(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    )

    title = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    posted_date = models.DateField(auto_now_add=True)
    deadline_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    client = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='jobs')
    max_freelancers = models.IntegerField(default=1)
    
    
    @property
    def is_max_freelancers_reached(self):
        return self.attempts.count() >= self.max_freelancers

    def __str__(self):
        return self.title
    
class Response(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    password = models.CharField(max_length=10)
    security_answer = models.CharField(max_length=100)
    number_of_items = models.IntegerField()
    phone_number = models.CharField(max_length=15)
    device_used = models.CharField(max_length=50)
    screenshot = models.ImageField(upload_to='response_screenshots/')

class JobAttempt(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attempts')
    freelancer = models.ForeignKey(Profile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'freelancer',)

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    job = models.ForeignKey('Job', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message}"