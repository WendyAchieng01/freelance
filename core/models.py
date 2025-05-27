from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from accounts.models import Profile
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


# Create your models here
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
    preferred_freelancer_level = models.CharField(max_length=50, choices=(
        ('entry', 'Entry Level'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert')
    ), default='intermediate')
    
    # New field to track selected freelancer
    selected_freelancer = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='selected_jobs'
    )
    
    # New field to track payment status (optional, depending on your payment flow)
    payment_verified = models.BooleanField(default=False)
    
    @property
    def is_max_freelancers_reached(self):
        return self.responses.count() >= self.max_freelancers
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
    
    
"""JobAssignment is used in the wallet app to automatically track jobs assigned to a freelancer"""


class JobAssignment(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    freelancer = models.ForeignKey(Profile, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending')

    class Meta:
        unique_together = ['job', 'freelancer']


class Response(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, related_name='responses', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(null=True, blank=True) 


    class Meta:
        unique_together = ('job', 'user',)

    def __str__(self):
        return f"Response by {self.user.username} for {self.job.title}"


class Chat(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='chats')
    client = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='client_chats')
    freelancer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='freelancer_chats')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat between {self.client.user.username} and {self.freelancer.user.username} for {self.job.title}"

class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"

class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to='chat_attachments/%Y/%m/%d/',
        validators=[FileExtensionValidator(
            allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx']
        )]
    )
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField()  # Size in bytes
    content_type = models.CharField(max_length=100)

    def __str__(self):
        return f"Attachment: {self.filename}"
    
class Review(models.Model):
    RATING_CHOICES = (
        (1, '1 - Poor'),
        (2, '2 - Below Average'),
        (3, '3 - Average'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    )
    
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reviews_given', on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reviews_received', on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('reviewer', 'recipient')  # Prevents multiple reviews from same user
    
    def __str__(self):
        return f"{self.reviewer.username}'s review for {self.recipient.username}"