from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Profile


# Create your models her
class Job(models.Model):
    CATEGORY_CHOICES = (
        ('data_entry', 'Data Entry'),
        ('translation', 'Translation'),
        ('transcription', 'Transcription and Captioning'),
        ('graphics', 'Graphics'),
        ('writing', 'Writing and Editing'),
        ('web_dev', 'App and Web Development'),
        ('project_mgmt', 'IT Project Management'),
        ('testing', 'Software Testing'),
        ('virtual_assist', 'Virtual Assistance'),
        ('social_media', 'Social Media Management'),
        ('ai_training', 'AI Model Training'),
    )

    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    )

    title = models.CharField(max_length=100)
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES
    )
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
        return f"{self.title} ({self.get_category_display()})"  

class Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, related_name='responses', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(null=True, blank=True) 


    class Meta:
        unique_together = ('job', 'user',)

    def __str__(self):
        return f"Response by {self.user.username} for {self.job.title}"

class JobAttempt(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attempts')
    freelancer = models.ForeignKey(Profile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'freelancer',)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    notification_type = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"
        