from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.utils.text import slugify
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
import uuid


def generate_unique_pay_id():
    """Generate a unique 10-digit number from UUID."""
    return str(uuid.uuid4().int)[:10]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_modified = models.DateTimeField(auto_now=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pic/', blank=True, null=True)
    pay_id = models.CharField(max_length=20, choices=(('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')), default='M-Pesa')
    id_card = models.CharField(max_length=10, blank=True)
    user_type = models.CharField(max_length=20, choices=(('freelancer', 'Freelancer'), ('client', 'Client')), default='freelancer')
    email_verified = models.BooleanField(default=False)
    device = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = (('user', 'user_type'), )
        
    def __str__(self):
        return self.user.username


class FreelancerProfile(models.Model):
    profile = models.OneToOneField('Profile', on_delete=models.CASCADE, related_name='freelancer_profile')
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

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='client_profile')
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
    project_media = models.FileField(
        upload_to=project_media_upload_path,
        blank=True,
        null=True
    )
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
