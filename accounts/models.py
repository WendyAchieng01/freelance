import uuid
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from cloudinary.models import CloudinaryField
from django.db.models.signals import post_save
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def generate_unique_pay_id():
    """Generate a unique 10-digit number from UUID."""
    return str(uuid.uuid4().int)[:10]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_modified = models.DateTimeField(auto_now=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    profile_pic = CloudinaryField(
        'image', folder='freelance/profile_pic/', null=True, blank=True, resource_type='raw')
    pay_id = models.CharField(max_length=20, choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), default='M-Pesa')
    id_card = models.CharField(max_length=10, blank=True)
    user_type = models.CharField(max_length=20, choices=(('freelancer', 'Freelancer'), ('client', 'Client')), default='freelancer')
    email_verified = models.BooleanField(default=False)
    device = models.CharField(max_length=100, blank=True)
        
    def __str__(self):
        return self.user.username


class FreelancerProfile(models.Model):
    profile = models.OneToOneField('Profile', on_delete=models.CASCADE,
                                related_name='freelancer_profile', limit_choices_to={'user_type': 'freelancer'})
    skills = models.ManyToManyField('Skill', blank=True)
    languages = models.ManyToManyField('Language', blank=True)
    portfolio_link = models.URLField(blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    availability = models.CharField(
        max_length=50,
        choices=(
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('weekends', 'Weekends Only'),
            ('custom', 'Custom Schedule'),
            ('not_available', 'Not Available')
        ),
        default='full_time'
    )
    is_visible = models.BooleanField(default=True)
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(
                f"{self.profile.user.username}-{self.hourly_rate}-{self.availability}-{self.id}")


        # Always generate portfolio_link from the slug
        self.portfolio_link = self.get_absolute_url(full=True)

        super().save(*args, **kwargs)

    def get_absolute_url(self, full=False):
        """
        Returns either a relative or full URL to the portfolio page.
        `full=True` will include the domain.
        """
        path = reverse("freelancer-portfolio",
                    kwargs={"username": self.profile.user.username})
        domain = settings.FRONTEND_URL.rstrip('/')
        return f"{domain}{path}" if full else path

    def __str__(self):
        return f"{self.profile.user.first_name}- {self.profile.user.last_name} ({self.hourly_rate}/hr - {self.availability})"


class ClientProfile(models.Model):
    INDUSTRY_CHOICES = (
        ('technology', 'Technology'),
        ('finance', 'Finance'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufacturing'),
        ('entertainment', 'Entertainment'),
        ('marketing', 'Marketing'),
        ('consulting', 'Consulting'),
        ('non_profit', 'Non-Profit'),
        ('government', 'Government'),
        ('legal', 'Legal Services'),
        ('real_estate', 'Real Estate'),
        ('hospitality', 'Hospitality'),
        ('transportation', 'Transportation'),
        ('agriculture', 'Agriculture'),
        ('energy', 'Energy'),
        ('telecom', 'Telecommunications'),
        ('media', 'Media'),
        ('other', 'Other'),
    )

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE,
                                   related_name='client_profile', limit_choices_to={'user_type': 'client'})
    company_name = models.CharField(max_length=200, blank=True)
    company_website = models.URLField(
        blank=True, null=True, help_text="Enter URL in the format https://nilltechsolutions.com/")
    industry = models.CharField(max_length=100, choices=INDUSTRY_CHOICES, blank=True)
    project_budget = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    preferred_freelancer_level = models.CharField(max_length=50, choices=(
        ('entry', 'Entry Level'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert')
    ), default='intermediate')
    languages = models.ManyToManyField('Language', blank=True)  

    slug = models.SlugField(unique=True, blank=True, null=True)
    is_verified = models.BooleanField(default=False,null=True,blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Save first to get ID
        if not self.slug:
            self.slug = slugify(
                f"{self.profile.user.username}-{self.company_name}-{self.industry}-{self.id}")
            ClientProfile.objects.filter(pk=self.pk).update(slug=self.slug)

    def get_absolute_url(self, full=False):
        """
        Returns either a relative or full URL to the portfolio page.
        `full=True` will include the domain.
        """
        path = reverse("client-portfolio",
                       kwargs={"username": self.profile.user.username})
        domain = settings.FRONTEND_URL.rstrip('/')
        return f"{domain}{path}" if full else path

    def __str__(self):
        return f"{self.profile.user.first_name}- {self.profile.user.last_name} ({self.company_name})"
    

class Skill(models.Model):
    SKILL_CHOICES = (
        # Programming Languages
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('java', 'Java'),
        ('csharp', 'C#'),
        ('cpp', 'C++'),
        ('php', 'PHP'),
        ('ruby', 'Ruby'),
        ('swift', 'Swift'),
        ('kotlin', 'Kotlin'),
        ('go', 'Go'),
        ('rust', 'Rust'),
        ('typescript', 'TypeScript'),
        
        # Web Development
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('react', 'React'),
        ('angular', 'Angular'),
        ('vue', 'Vue.js'),
        ('django', 'Django'),
        ('flask', 'Flask'),
        ('nodejs', 'Node.js'),
        ('express', 'Express.js'),
        ('spring', 'Spring Boot'),
        ('laravel', 'Laravel'),
        ('aspnet', 'ASP.NET'),
        ('jquery', 'jQuery'),
        ('bootstrap', 'Bootstrap'),
        ('tailwind', 'Tailwind CSS'),
        
        # Mobile Development
        ('android', 'Android Development'),
        ('ios', 'iOS Development'),
        ('flutter', 'Flutter'),
        ('reactnative', 'React Native'),
        ('xamarin', 'Xamarin'),
        
        # Databases
        ('sql', 'SQL'),
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('mongodb', 'MongoDB'),
        ('oracle', 'Oracle'),
        ('firebase', 'Firebase'),
        ('redis', 'Redis'),
        
        # Cloud & DevOps
        ('aws', 'AWS'),
        ('azure', 'Microsoft Azure'),
        ('gcp', 'Google Cloud'),
        ('docker', 'Docker'),
        ('kubernetes', 'Kubernetes'),
        ('jenkins', 'Jenkins'),
        ('gitops', 'GitOps'),
        ('terraform', 'Terraform'),
        ('ansible', 'Ansible'),
        
        # Data Science & AI
        ('python_data', 'Python for Data Science'),
        ('r', 'R Programming'),
        ('machine_learning', 'Machine Learning'),
        ('deep_learning', 'Deep Learning'),
        ('tensorflow', 'TensorFlow'),
        ('pytorch', 'PyTorch'),
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('scikit', 'Scikit-Learn'),
        ('nlp', 'Natural Language Processing'),
        ('computer_vision', 'Computer Vision'),
        
        # Design
        ('uiux', 'UI/UX Design'),
        ('graphic_design', 'Graphic Design'),
        ('figma', 'Figma'),
        ('adobe_xd', 'Adobe XD'),
        ('sketch', 'Sketch'),
        ('photoshop', 'Adobe Photoshop'),
        ('illustrator', 'Adobe Illustrator'),
        
        # Project Management
        ('agile', 'Agile Methodology'),
        ('scrum', 'Scrum'),
        ('kanban', 'Kanban'),
        ('jira', 'Jira'),
        ('confluence', 'Confluence'),
        ('trello', 'Trello'),
        ('asana', 'Asana'),
        
        # Other Technical Skills
        ('git', 'Git'),
        ('testing', 'Software Testing'),
        ('devops', 'DevOps'),
        ('cybersecurity', 'Cybersecurity'),
        ('blockchain', 'Blockchain'),
        ('seo', 'SEO'),
        ('data_analysis', 'Data Analysis'),
        ('technical_writing', 'Technical Writing'),
    )
    
    name = models.CharField(max_length=100, choices=SKILL_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()


class Language(models.Model):
    LANGUAGE_CHOICES = (
        ('english', 'English'),
        ('swahili', 'Swahili'),
        ('spanish', 'Spanish'),
        ('french', 'French'),
        ('german', 'German'),
        ('italian', 'Italian'),
        ('portuguese', 'Portuguese'),
        ('russian', 'Russian'),
        ('mandarin', 'Mandarin Chinese'),
        ('cantonese', 'Cantonese'),
        ('japanese', 'Japanese'),
        ('korean', 'Korean'),
        ('arabic', 'Arabic'),
        ('hindi', 'Hindi'),
        ('bengali', 'Bengali'),
        ('urdu', 'Urdu'),
        ('swahili', 'Swahili'),
        ('dutch', 'Dutch'),
        ('swedish', 'Swedish'),
        ('norwegian', 'Norwegian'),
        ('danish', 'Danish'),
        ('finnish', 'Finnish'),
        ('polish', 'Polish'),
        ('turkish', 'Turkish'),
        ('hebrew', 'Hebrew'),
        ('greek', 'Greek'),
        ('thai', 'Thai'),
        ('vietnamese', 'Vietnamese'),
        ('indonesian', 'Indonesian'),
        ('malay', 'Malay'),
        ('tagalog', 'Filipino/Tagalog'),
        ('czech', 'Czech'),
        ('slovak', 'Slovak'),
        ('hungarian', 'Hungarian'),
        ('romanian', 'Romanian'),
        ('bulgarian', 'Bulgarian'),
        ('ukrainian', 'Ukrainian'),
        ('farsi', 'Farsi/Persian'),
        ('afrikaans', 'Afrikaans'),
        ('amharic', 'Amharic'),
        ('other', 'Other'),
    )
    
    name = models.CharField(max_length=100, choices=LANGUAGE_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()

def create_profile(sender, instance, created, **kwargs):
    if created:
        user_profile = Profile(user=instance)
        user_profile.save()

post_save.connect(create_profile, sender=User)


def project_media_upload_path(instance, filename):
    return f'portfolio/{instance.user.username}/{filename}'


class PortfolioProject(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="portfolio_projects")
    freelancer = models.ForeignKey(
        "FreelancerProfile", on_delete=models.CASCADE, related_name="portfolio_projects", null=True, blank=True)
    project_title = models.CharField(max_length=200)
    role = models.CharField(max_length=100)
    description = models.TextField()
    link = models.URLField(blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)
    project_media = CloudinaryField(
        'file', folder='freelance/portfolio_media/', null=True, blank=True, resource_type='raw')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Portfolio Project"
        verbose_name_plural = "Portfolio Projects"
        ordering = ["-created_at"]

    def clean(self):
        """Ensure a user cannot have more than 4 portfolio projects."""
        if not self.pk and PortfolioProject.objects.filter(user=self.user).count() >= 4:
            raise ValidationError(
                "You can only add up to 4 portfolio projects.")

    def save(self, *args, **kwargs):
        if not self.slug or "update_fields" in kwargs and "project_title" in kwargs["update_fields"]:
            base_slug = slugify(self.project_title)
            unique_slug = base_slug
            num = 1
            while PortfolioProject.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug

        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project_title} ({self.user.username})"


class ContactUs(models.Model):
    CONTACT_CHOICES = (
        ('general', 'General Inquiry'),
        ('support', 'Technical Support'),
        ('billing', 'Billing Issue'),
        ('partnership', 'Partnership'),
        ('other', 'Other'),
    )

    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )

    # BASIC INFO 
    tracking_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField()

    # Improved phone validation (7-13 digits, optional +)
    phone_regex = RegexValidator(
        regex=r'^\+?\d{7,13}$',
        message="Phone number must contain 7–15 digits, optional leading +.",
    )
    phone = models.CharField(
        validators=[phone_regex], max_length=17, blank=True, null=True)

    # MESSAGE 
    subject = models.CharField(max_length=200)
    message = models.TextField()
    contact_type = models.CharField(
        max_length=20, choices=CONTACT_CHOICES, default='general')

    # META 
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='normal')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True, null=True)
    honeypot = models.CharField(max_length=100, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    submission_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False)

    # Optional attachment
    attachment = CloudinaryField(
        'attachment',folder='freelance/contact_attachments/',null=True,blank=True,
        resource_type='raw')

    # Optional tagging
    tags = models.CharField(max_length=255, blank=True,
                            help_text="Comma-separated tags")

    # Soft delete
    is_deleted = models.BooleanField(default=False)

    # STATUS 
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)

    # ADMIN RESPONSE 
    admin_notes = models.TextField(blank=True)
    response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_responses",
    )

    response_sent = models.BooleanField(default=False)
    response_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Contact Us Submission"
        verbose_name_plural = "Contact Us Submissions"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["email"]),
            models.Index(fields=["contact_type"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["is_read"]),
        ]

    # Methods
    def save(self, *args, **kwargs):
        # Auto-generate tracking ID if missing
        if not self.tracking_id:
            self.tracking_id = f"CNS-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tracking_id} | {self.name} - {self.subject}"

    def get_absolute_url(self):
        """
        Admin change URL (useful for notifications linking back to admin).
        Pattern: 'admin:<app_label>_<modelname>_change'
        """
        try:
            return reverse('admin:contact_contactus_change', args=[self.pk])
        except Exception:
            return "#"

    def to_dict(self):
        """Simple serializable representation (safe for APIs)"""
        return {
            "id": self.pk,
            "tracking_id": self.tracking_id,
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "contact_type": self.contact_type,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "is_read": self.is_read,
            "responded": self.responded,
            "response_sent": self.response_sent,
        }

    # STATUS HELPERS
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read"])

    def mark_as_responded(self, response_text="", notes="", user=None, send_email=True):
        """
        Mark this submission as responded to, set response fields and optionally send email.
        """
        self.responded = True
        self.responded_at = timezone.now()
        self.response = response_text or self.response
        self.responded_by = user or self.responded_by

        if notes:
            # append notes rather than overwrite if desired; here we overwrite to match original behavior
            self.admin_notes = notes

        if send_email and response_text and self.email:
            self.send_response_email(response_text)

        self.save()

    def get_status_display(self):
        """Get human-readable status"""
        if self.responded:
            return "Responded"
        elif self.is_read:
            return "Read"
        else:
            return "New"

    def get_priority_badge(self):
        """Return CSS class for priority badge"""
        priority_classes = {
            "low": "badge-info",
            "normal": "badge-secondary",
            "high": "badge-warning",
            "urgent": "badge-danger",
        }
        return priority_classes.get(self.priority, "badge-secondary")

    # ANALYTICS HELPERS
    @property
    def month(self):
        return self.timestamp.month

    @property
    def year(self):
        return self.timestamp.year

    # USER HELPERS
    @classmethod
    def get_user_inquiries(cls, user):
        """Get all contact inquiries for a specific user based on email match (non-deleted)."""
        return cls.objects.filter(email=user.email, is_deleted=False)

    def belongs_to_user(self, user):
        """Check if this contact inquiry belongs to the given user."""
        return self.email == user.email

    # EMAIL / RESPONSE
    def send_response_email(self, response_text):
        """
        Send professional email response using EmailMultiAlternatives.
        Tries to render templates if they exist, otherwise falls back to inline generator methods.
        """
        try:
            current_site = Site.objects.get_current()
        except Exception:
            current_site = None

        platform_name = getattr(
            settings, "PLATFORM_NAME", (current_site.name if current_site else "Our Platform"))
        support_email = getattr(
            settings, "SUPPORT_EMAIL", "support@example.com")

        subject = f"Re: {self.subject}"

        context = {
            "name": self.name,
            "original_message": self.message,
            "response": response_text,
            "submission_date": self.timestamp,
            "contact_type": self.get_contact_type_display(),
            "platform_name": platform_name,
            "current_site": current_site,
            "support_email": support_email,
            "tracking_id": self.tracking_id,
            "response_by": getattr(self.responded_by, "get_full_name", lambda: None)() if self.responded_by else None,
        }

        # Prefer template-based email if templates are present; if not, use inline generators.
        text_content = None
        html_content = None
        try:
            # You can place templates at:
            # templates/emails/contact_response.txt and templates/emails/contact_response.html
            text_content = render_to_string(
                "emails/contact_response.txt", context).strip()
            html_content = render_to_string(
                "emails/contact_response.html", context)
        except Exception:
            text_content = self._generate_text_email(context)
            html_content = self._generate_html_email(context)

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                to=[self.email],
                reply_to=[support_email]
            )

            # attach HTML if available
            if html_content:
                email.attach_alternative(html_content, "text/html")

            # attach any uploaded attachment (optional; ensure proper permissions/security)
            if self.attachment:
                try:
                    email.attach(self.attachment.name, self.attachment.read())
                except Exception:
                    # if attachment read fails, continue without attachment
                    pass

            email.send(fail_silently=False)

            # Update tracking
            self.response_sent = True
            self.response_sent_at = timezone.now()
            self.save(update_fields=["response_sent", "response_sent_at"])

            return True
        except Exception as e:
            # Log exception as needed. Print for simplicity here.
            print(f"Failed to send response email: {e}")
            return False

    def _generate_text_email(self, context):
        """Generate plain text email content"""
        return f"""
                Hi {context['name']},
                Thank you for contacting us regarding your {context['contact_type']} inquiry.
                Here is our response:
                {context['response']}
                Your original message: coming from models now
                {context['original_message']}
                Submitted on: {context['submission_date'].strftime('%B %d, %Y')}
                If you have any further questions, please don't hesitate to contact us again.
                Best regards,
                The {context['platform_name']} Team
                ---
                This is an automated response. Please do not reply to this email.
                © {context['submission_date'].year} {context['platform_name']}. All rights reserved.
                """

    def _generate_html_email(self, context):
        """Generate professional HTML email content (fallback)"""
        site_link = ""
        if context.get("current_site") and getattr(context["current_site"], "domain", None):
            site_link = f"https://{context['current_site'].domain}"
        return f"""
                <!DOCTYPE html>
                <html>
                <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>Response to Your Inquiry</title>
                <style>
                    body {{ font-family: Arial, sans-serif; color: #333; background: #f8f9fa; margin:0; padding:0; }}
                    .container {{ max-width:600px; margin:20px auto; background:#fff; padding:24px; border-radius:6px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
                    .header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:20px; border-radius:6px 6px 0 0; text-align:center }}
                    .content {{ padding:16px; color:#495057; line-height:1.6 }}
                    .response {{ background:#f8f9fa; padding:12px; border-left:4px solid #667eea; border-radius:4px }}
                    .original {{ background:#fff3cd; padding:12px; border-left:4px solid #ffc107; border-radius:4px }}
                    .footer {{ font-size:13px; color:#6c757d; text-align:center; padding-top:12px }}
                    .button {{ display:inline-block; padding:10px 18px; color:#fff; background:#667eea; border-radius:6px; text-decoration:none }}
                </style>
                </head>
                <body>
                <div class="container">
                <div class="header">
                    <h2 style="margin:0">Response to Your Inquiry from </h2>
                    <div style="opacity:.9; margin-top:6px">{context['platform_name']} Support Team</div>
                </div>
                <div class="content">
                    <p>Hi <strong>{context['name']}</strong>,</p>
                    <p>Thank you for contacting us regarding your <strong>{context['contact_type']}</strong> inquiry.</p>

                    <div class="response">
                    <h4 style="margin:0 0 8px 0;">Our Response</h4>
                    <div>{context['response'].replace('\\n', '<br>')}</div>
                    </div>

                    <div style="margin-top:14px" class="original">
                    <h5 style="margin:0 0 6px 0;">Your Original Message</h5>
                    <div style="font-style:italic">{context['original_message'].replace('\\n', '<br>')}</div>
                    <p style="margin-top:8px; font-size:13px; color:#856404">Submitted on: {context['submission_date'].strftime('%B %d, %Y at %I:%M %p')}</p>
                    </div>

                    <div style="text-align:center; margin-top:18px;">
                    <a href="{site_link or '#'}" class="button">Visit Our Platform</a>
                    </div>

                    <div style="margin-top:18px; padding:12px; background:#e7f3ff; border-radius:6px; text-align:center;">
                    Need immediate assistance? Email us at: {context['support_email']}
                    </div>
                </div>

                <div class="footer">
                    <p style="margin:8px 0"><strong>{context['platform_name']}</strong></p>
                    <p style="margin:0">This is an automated message. Please do not reply to this email.<br>© {context['submission_date'].year} {context['platform_name']}. All rights reserved.</p>
                </div>
                </div>
                </body>
                </html>"""
