import uuid
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
import logging

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
    selected_freelancer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='selected_jobs')
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
        """
        Marks the job as completed if all conditions are met.
        """
        if self.status == 'completed':
            return False  # Already completed

        if not force:
            # Only allow marking as completed if in progress
            if self.status != 'in_progress':
                return False

            # Only allow if payment has been verified
            if not self.payment_verified:
                return False

            # Must have a selected freelancer to complete the job
            if not self.selected_freelancer < self.required_freelancers:
                return False


        self.status = 'completed'
        self.save(update_fields=['status'])
        return True
    
    def add_selected_freelancer(self, user):
        """
        Adds a freelancer to selected_freelancers if limit not exceeded.
        Returns True if added, False otherwise.
        """
        if self.selected_freelancers.filter(id=user.id).exists():
            return False  # Already selected

        if self.selected_freelancers.count() >= self.required_freelancers:
            return False  # Limit reached

        self.selected_freelancers.add(user)
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
        
        # Detect changes in selected_freelancer
        if self.pk: 
            old_job = Job.objects.filter(pk=self.pk).only(
                "selected_freelancer").first()
            if old_job and old_job.selected_freelancer != self.selected_freelancer:
                if self.selected_freelancer:
                    # new freelancer assigned
                    from django.utils import timezone
                    self.assigned_at = timezone.now()
                else:
                    # freelancer unassigned (reset assignment date)
                    self.assigned_at = None
        else:
            # new job creation with freelancer pre-set
            if self.selected_freelancer and not self.assigned_at:
                from django.utils import timezone
                self.assigned_at = timezone.now()
        
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job = models.ForeignKey('Job', related_name='responses', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=150)
    cv = models.FileField(
        upload_to='response_attachments/cvs/%Y/%m/%d/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    cover_letter = models.FileField(
        upload_to='response_attachments/cover_letters/%Y/%m/%d/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])]
    )
    portfolio = models.FileField(
        upload_to='response_attachments/portfolios/%Y/%m/%d/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'zip'])]
    )
    cv_size = models.IntegerField(null=True, blank=True)  # Store file size
    cover_letter_size = models.IntegerField(null=True, blank=True)
    portfolio_size = models.IntegerField(null=True, blank=True)
    cv_content_type = models.CharField(max_length=100, null=True, blank=True)  # MIME type
    cover_letter_content_type = models.CharField(max_length=100, null=True, blank=True)
    portfolio_content_type = models.CharField(max_length=100, null=True, blank=True)
    portfolio_thumbnail = models.ImageField(
        upload_to='response_attachments/thumbnails/%Y/%m/%d/',
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
        # Set file metadata
        if self.cv and not self.cv_size:
            self.cv_size = self.cv.size
            self.cv_content_type = self.cv.file.content_type
        if self.cover_letter and not self.cover_letter_size:
            self.cover_letter_size = self.cover_letter.size
            self.cover_letter_content_type = self.cover_letter.file.content_type
        if self.portfolio and not self.portfolio_size:
            self.portfolio_size = self.portfolio.size
            self.portfolio_content_type = self.portfolio.file.content_type

        # Upload files to Cloudinary
        for field in ['cv', 'cover_letter', 'portfolio']:
            file_field = getattr(self, field)
            if file_field and not getattr(self, f'{field}_size'):
                upload_path = datetime.now().strftime(f'response_attachments/{field}s/%Y/%m/%d/')
                file_name = os.path.basename(file_field.name)
                public_id = f"{upload_path}{file_name}"
                try:
                    upload_result = upload(
                        file_field,
                        public_id=public_id,
                        resource_type="auto",
                        overwrite=True
                    )
                    setattr(self, field, upload_result['public_id'])
                    setattr(self, f'{field}_size', upload_result.get('bytes'))
                    setattr(self, f'{field}_content_type', upload_result.get('resource_type'))
                except Exception as e:
                    print(f"Cloudinary upload failed for {field}: {e}")
                    raise

        # Generate thumbnail for portfolio if it's an image
        if self.portfolio and self.portfolio_content_type.startswith('image/') and not self.portfolio_thumbnail:
            try:
                img = Image.open(self.portfolio)
                img.thumbnail((200, 200))
                thumb_io = BytesIO()
                img.save(thumb_io, format=img.format)
                thumb_filename = f'thumb_{os.path.basename(self.portfolio.name)}'
                thumb_public_id = f'response_attachments/thumbnails/{datetime.now().strftime("%Y/%m/%d")}/{thumb_filename}'
                thumb_upload = upload(
                    thumb_io.getvalue(),
                    public_id=thumb_public_id,
                    resource_type="image",
                    overwrite=True
                )
                self.portfolio_thumbnail = thumb_upload['public_id']
            except Exception as e:
                print(f"Thumbnail generation failed: {e}")

        # Auto-generate slug
        if not self.slug:
            base_slug = slugify(f'{self.job.title}-{self.user.username}')
            unique_slug = base_slug
            num = 1
            while Response.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{num}'
                num += 1
            self.slug = unique_slug

        # Auto-update response status
        self.auto_update_status()
        super().save(*args, **kwargs)

    def auto_update_status(self):
        """Automate response status updates based on job state."""
        if self.job.status == 'completed' and self.status not in ['rejected', 'accepted']:
            self.status = 'rejected' 

        elif self.job.selected_freelancer == self.user:
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
    message = models.ForeignKey('Message', on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to='chat_attachments/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'])]
    )
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField()
    content_type = models.CharField(max_length=100)
    thumbnail = models.ImageField(
        upload_to='chat_attachments/thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Auto-generated thumbnail for image files"
    )

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name
            self.file_size = self.file.size
            self.content_type = getattr(self.file, 'content_type', 'application/octet-stream')

        # Generate folder path dynamically
        upload_path = datetime.now().strftime('chat_attachments/%Y/%m/%d/')
        file_name = os.path.basename(self.filename)
        public_id = f"{upload_path}{file_name}"

        # Upload file to Cloudinary with the correct public_id
        if self.file and not self.pk:  # Only upload on creation
            try:
                upload_result = upload(
                    self.file,
                    public_id=public_id,
                    resource_type="auto",  # Automatically detect file type
                    overwrite=True
                )
                self.file = upload_result['public_id']  # Store Cloudinary public_id
                self.file_size = upload_result.get('bytes', self.file_size)
                self.content_type = upload_result.get('resource_type', self.content_type)
            except Exception as e:
                print(f"Cloudinary upload failed: {e}")
                raise

        # Generate thumbnail for images
        if self.content_type.startswith('image/') and not self.thumbnail:
            try:
                img = Image.open(self.file)
                img.thumbnail((200, 200))
                thumb_io = BytesIO()
                img.save(thumb_io, format=img.format)
                thumb_filename = f'thumb_{file_name}'
                thumb_public_id = f'chat_attachments/thumbnails/{datetime.now().strftime("%Y/%m/%d")}/{thumb_filename}'
                thumb_upload = upload(
                    thumb_io.getvalue(),
                    public_id=thumb_public_id,
                    resource_type="image",
                    overwrite=True
                )
                self.thumbnail = thumb_upload['public_id']
            except Exception as e:
                print(f"Thumbnail generation failed: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment: {self.filename}"


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
    file = models.FileField(
        upload_to='response_attachments/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'zip'])]
    )
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name
            self.file_size = self.file.size
            self.content_type = getattr(self.file, 'content_type', 'application/octet-stream')

        # Generate folder path dynamically
        upload_path = datetime.now().strftime('response_attachments/%Y/%m/%d/')
        file_name = os.path.basename(self.filename)
        public_id = f"{upload_path}{file_name}"

        # Upload file to Cloudinary with the correct public_id
        if self.file and not self.pk:  # Only upload on creation
            try:
                upload_result = upload(
                    self.file,
                    public_id=public_id,
                    resource_type="auto",
                    overwrite=True
                )
                self.file = upload_result['public_id']
                self.file_size = upload_result.get('bytes', self.file_size)
                self.content_type = upload_result.get('resource_type', self.content_type)
            except Exception as e:
                print(f"Cloudinary upload failed: {e}")
                raise

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment: {self.filename} for Response {self.response.id}"