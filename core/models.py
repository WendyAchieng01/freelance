import uuid
import mimetypes
import cloudinary
import cloudinary.uploader
from django.db import models
from django.conf import settings
from django.db.models import Avg
from django.utils import timezone
from accounts.models import Profile
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from datetime import timedelta
from accounts.models import Skill
from django.utils.timezone import now
from .choices import CATEGORY_CHOICES,APPLICATION_STATUS_CHOICES,JOB_STATUS_CHOICES,EXPERIENCE_LEVEL
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from cloudinary.uploader import upload
import os
from datetime import datetime
from cloudinary import uploader
from mimetypes import guess_type
import logging
from cloudinary.models import CloudinaryField
logger = logging.getLogger(__name__)

class JobCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Job(models.Model):
    title = models.CharField(max_length=100)
    category = models.ForeignKey(JobCategory, on_delete=models.SET_NULL, null=True, related_name='jobs')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    posted_date = models.DateTimeField(auto_now_add=True)
    deadline_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default='open')
    client = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='jobs')
    max_freelancers = models.IntegerField(default=1, help_text="Set total number of applications to receive")
    required_freelancers = models.PositiveSmallIntegerField(default=1, help_text="If the job requires more than one freelancer")
    skills_required = models.ManyToManyField(Skill, related_name="required_skills")
    preferred_freelancer_level = models.CharField(max_length=50, choices=EXPERIENCE_LEVEL, default='intermediate')
    reviewed_responses = models.ManyToManyField('Response', related_name='marked_jobs', blank=True)
    selected_freelancers = models.ManyToManyField(User,blank=True,related_name='selected_jobs')
    assigned_at = models.DateTimeField(null=True, blank=True, help_text="When a freelancer was assigned")
    payment_verified = models.BooleanField(default=False)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)  

    
    def get_absolute_url(self):
        if self.slug:
            return reverse('job-detail-slug', kwargs={'slug': self.slug})
        return reverse('job-detail-id', kwargs={'id': self.id})
    
    def get_payment_url(self):
        """
        Returns the absolute URL to initiate payment for this job.
        Priority: use slug if available; otherwise, fallback to id.
        """
        if self.slug:
            return reverse('payment-initiate-slug', kwargs={'slug': self.slug})
        return reverse('payment-initiate-id', kwargs={'id': self.id})
    
    def mark_as_completed(self, force=True):
        if self.status == 'completed':
            return False

        if not force:
            if self.status != 'in_progress':
                return False

            if not self.payment_verified:
                return False

            # Must have required number of freelancers
            if self.selected_freelancers.count() < self.required_freelancers:
                return False

        self.status = 'completed'
        self.save(update_fields=['status'])
        return True

    def add_selected_freelancer(self, user):
        """
        Adds a freelancer if limit not exceeded.
        """
        if self.selected_freelancers.filter(id=user.id).exists():
            return False  # Already selected

        if self.selected_freelancers.count() >= self.required_freelancers:
            return False  # Limit reached

        self.selected_freelancers.add(user)

        if self.status != 'in_progress':
            self.status = 'in_progress'
            self.save(update_fields=['status'])

        return True


    def mark_response_for_review(self, response):
        if response.job != self:
            raise ValidationError("Cannot mark response for a different job.")
        self.reviewed_responses.add(response)
    
    
    @property
    def is_max_freelancers_reached(self):
        return self.responses.count() >= self.max_freelancers
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            unique_slug = base_slug
            num = 1
            while Job.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{num}'
                num += 1
            self.slug = unique_slug

        super().save(*args, **kwargs)

    
    def __str__(self):
        try:
            return f"{self.title} ({self.get_category_display()})"
        except Exception:
            return self.title or "Untitled Job"


class JobBookmark(models.Model):
    user = models.ForeignKey( User, on_delete=models.CASCADE, related_name='bookmarks')
    job = models.ForeignKey('Job', on_delete=models.CASCADE, related_name='bookmarked_by')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')

    def __str__(self):
        return f"{self.user.username} bookmarked {self.job.title}"


class Response(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    job = models.ForeignKey(
        'Job', related_name='responses', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=150)
    cv = CloudinaryField(
        'file',
        folder='freelance/response_attachments/cvs',
        resource_type='raw',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    cover_letter = CloudinaryField(
        'file',
        folder='freelance/response_attachments/cover_letters',
        resource_type='raw',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    portfolio = CloudinaryField(
        'file',
        folder='freelance/response_attachments/portfolios',
        resource_type='raw',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'zip'])]
    )
    cv_size = models.IntegerField(null=True, blank=True)
    cover_letter_size = models.IntegerField(null=True, blank=True)
    portfolio_size = models.IntegerField(null=True, blank=True)
    cv_content_type = models.CharField(
        max_length=100, null=True, blank=True)  # MIME type
    cover_letter_content_type = models.CharField(
        max_length=100, null=True, blank=True)
    portfolio_content_type = models.CharField(
        max_length=100, null=True, blank=True)
    portfolio_thumbnail = CloudinaryField(
        'image',
        folder='freelance/response_attachments/thumbnails',
        resource_type='image',
        null=True,
        blank=True,
        help_text="Auto-generated thumbnail for portfolio images"
    )
    status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS_CHOICES, default='submitted',
        null=True, blank=True
    )
    marked_for_review = models.BooleanField(default=False)

    class Meta:
        unique_together = ('job', 'user',)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f'{self.job.title}-{self.user.username}')
            unique_slug = base_slug
            num = 1
            while Response.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{num}'
                num += 1
            self.slug = unique_slug

        # Auto update status before saving
        self.auto_update_status()

        # First save, so Cloudinary actually uploads and assigns public_id
        super().save(*args, **kwargs)

        # Now metadata fetching can work
        for field in ['cv', 'cover_letter', 'portfolio']:
            file_field = getattr(self, field)
            if file_field and not getattr(self, f'{field}_size'):
                try:
                    resource = cloudinary.api.resource(
                        file_field.public_id,
                        resource_type='raw' if field != 'portfolio_thumbnail' else 'image'
                    )
                    setattr(self, f'{field}_size', resource.get('bytes'))
                    setattr(self, f'{field}_content_type',
                            resource.get('resource_type'))
                except Exception as e:
                    print(f"Failed to fetch metadata for {field}: {e}")

        # Portfolio thumbnail generation (only after Cloudinary upload)
        if (
            self.portfolio
            and getattr(self, 'portfolio_content_type', None)
            and self.portfolio_content_type.startswith('image/')
            and not self.portfolio_thumbnail
        ):
            try:
                thumb_public_id = (
                    f'freelance/response_attachments/thumbnails/'
                    f'{datetime.now().strftime("%Y/%m/%d")}/'
                    f'thumb_{self.portfolio.public_id.split("/")[-1]}'
                )
                upload_result = cloudinary.uploader.upload(
                    self.portfolio.url,
                    public_id=thumb_public_id,
                    resource_type='image',
                    transformation=[
                        {'width': 200, 'height': 200, 'crop': 'thumb'}],
                    overwrite=True,
                )
                self.portfolio_thumbnail = upload_result['public_id']
                super().save(update_fields=['portfolio_thumbnail'])
            except Exception as e:
                print(f"Thumbnail generation failed: {e}")

    def auto_update_status(self):
        """Automate response status updates based on job state."""
        if self.job.status == 'completed' and self.status not in ['rejected', 'accepted']:
            self.status = 'rejected'

        elif self.job.selected_freelancers.filter(id=self.user_id).exists():
            # This user is one of the selected freelancers
            self.status = 'accepted'

        elif self.job.status == 'in_progress' and self.status == 'submitted':
            self.status = 'under_review'

    def is_accepted(self):
        return self.status == 'accepted'

    def is_rejected(self):
        return self.status == 'rejected'

    def is_under_review(self):
        return self.status == 'under_review'

    def is_submitted(self):
        return self.status == 'submitted'

    def mark_for_review(self):
        self.marked_for_review = True
        self.status = 'under_review'
        self.save()

    def unmark_review(self):
        self.marked_for_review = False
        if self.status == 'under_review':
            self.status = 'submitted'
        self.save()

    def __str__(self):
        return f"Response by {self.user.username} for {self.job.title}"


class Chat(models.Model):
    chat_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='chats')
    client = models.ForeignKey(Profile, on_delete=models.DO_NOTHING, related_name='client_chats')
    freelancer = models.ForeignKey(Profile, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='freelancer_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('job', 'client', 'freelancer')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(
                f"{self.job.id}-{self.client.id}-{self.freelancer.id if self.freelancer else 'none'}-{uuid.uuid4().hex[:8]}")
        super().save(*args, **kwargs)

    def can_access(self, user):
        return user == self.client.user or (self.freelancer and user == self.freelancer.user)

    def get_other_participant(self, user):
        if user == self.client.user:
            return self.freelancer.user if self.freelancer else None
        elif self.freelancer and user == self.freelancer.user:
            return self.client.user
        return None

    def get_last_message(self):
        return self.messages.order_by('-timestamp').first()

    def get_unread_count(self, user):
        if not self.can_access(user):
            return 0
        other = self.get_other_participant(user)
        if other:
            return self.messages.filter(sender=other, is_read=False).count()
        return 0

    def archive(self):
        self.active = False
        self.save()

    def __str__(self):
        freelancer_username = self.freelancer.user.username if self.freelancer else "No Freelancer"
        return f"Chat between {self.client.user.username} and {freelancer_username} for {self.job.title}"



class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def can_edit(self, user):
        time_limit = timezone.now() - timedelta(minutes=5)
        return user == self.sender and self.timestamp > time_limit

    def can_delete(self, user):
        time_limit = timezone.now() - timedelta(minutes=5)
        return user == self.sender and self.timestamp > time_limit and not self.is_deleted

    @property
    def has_attachments(self):
        return self.attachments.exists()

    def get_attachment_urls(self):
        return [reverse('serve_attachment', args=[a.id]) for a in self.attachments.all()]

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"
    

class MessageAttachment(models.Model):
    message = models.ForeignKey(
        'Message', on_delete=models.CASCADE, related_name='attachments')
    file = CloudinaryField(
        'file',
        folder='freelance/chat_attachments',
        resource_type='raw',
        validators=[FileExtensionValidator(allowed_extensions=[
                                            'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'])],
        null=True,
        blank=True
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    thumbnail = CloudinaryField(
        'image',
        folder='freelance/chat_attachments/thumbnails',
        resource_type='image',
        null=True,
        blank=True,
        help_text="Auto-generated thumbnail for image files"
    )

    def save(self, *args, **kwargs):
        # Set filename if not already set
        if self.file and not self.filename:
            self.filename = self.file.public_id.split('/')[-1]

        # Set file metadata (size and content type)
        if self.file and not self.file_size:
            try:
                resource = cloudinary.api.resource(
                    self.file.public_id, resource_type='raw')
                self.file_size = resource.get('bytes')
                self.content_type = resource.get('resource_type')
            except Exception as e:
                print(f"Failed to fetch metadata for file: {e}")
                # Log error (handled by settings.LOGGING)

        # Generate thumbnail for images
        if self.file and self.content_type and self.content_type.startswith('image/') and not self.thumbnail:
            try:
                thumb_public_id = f'freelance/chat_attachments/thumbnails/{datetime.now().strftime("%Y/%m/%d")}/thumb_{self.file.public_id.split("/")[-1]}'
                upload_result = cloudinary.uploader.upload(
                    self.file.url,
                    public_id=thumb_public_id,
                    resource_type='image',
                    transformation=[
                        {'width': 200, 'height': 200, 'crop': 'thumb'}],
                    overwrite=True
                )
                self.thumbnail = upload_result['public_id']
            except Exception as e:
                print(f"Thumbnail generation failed: {e}")
                # Log error (handled by settings.LOGGING)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment: {self.filename or 'Unnamed'}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    chat = models.ForeignKey(
        Chat, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.user.username}"


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
        verbose_name_plural = 'Review'
        #unique_together = ('reviewer', 'recipient') 
        
    @classmethod
    def average_rating_for(cls, user):
        return cls.objects.filter(recipient=user).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0

    @classmethod
    def review_count_for(cls, user):
        return cls.objects.filter(recipient=user).count()

    @classmethod
    def reviews_for(cls, user):
        return cls.objects.filter(recipient=user).order_by('-created_at')

    @classmethod
    def recent_reviews_for(cls, user, limit=7):
        return cls.reviews_for(user)[:limit]
    
    def __str__(self):
        return f"{self.reviewer.username}'s review for {self.recipient.username}"


class ResponseAttachment(models.Model):
    response = models.ForeignKey(
        'Response',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = CloudinaryField(
        'file',
        folder='freelance/response_attachments',
        resource_type='raw',
        validators=[FileExtensionValidator(
            allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'zip'])],
        null=True,
        blank=True
    )
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Set filename if not already set
        if self.file and not self.filename:
            self.filename = self.file.public_id.split('/')[-1]

        # Set file metadata (size and content type)
        if self.file and not self.file_size:
            try:
                resource = cloudinary.api.resource(
                    self.file.public_id, resource_type='raw')
                self.file_size = resource.get('bytes')
                self.content_type = resource.get('resource_type')
            except Exception as e:
                print(f"Failed to fetch metadata for file: {e}")
                # Log error (handled by settings.LOGGING)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment: {self.filename or 'Unnamed'} for Response {self.response.id}"
