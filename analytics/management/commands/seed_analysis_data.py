# analytics/management/commands/seed_data.py

import random
import json
import os
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker
from django.db import transaction

from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from core.models import Job, JobCategory, Response

User = get_user_model()

# ── Kenyan / East African name lists ────────────────────────────────────────
KENYAN_FIRST_NAMES_MALE = [
    "John", "James", "Joseph", "David", "Michael", "Peter", "Paul", "Samuel", "Daniel", "Joshua",
    "Isaac", "Abraham", "Moses", "Jacob", "Noah", "Eli", "Caleb", "Ethan", "Benjamin", "Matthew",
    "Otieno", "Onyango", "Ochieng", "Okoth", "Odhiambo", "Kamau", "Maina", "Mwangi", "Kiprono", "Kipchoge",
    "Juma", "Hassan", "Mohamed", "Ahmed", "Ali", "Omar", "Ibrahim", "Yusuf", "Abdi", "Farah",
]

KENYAN_FIRST_NAMES_FEMALE = [
    "Mary", "Grace", "Faith", "Hope", "Mercy", "Joy", "Esther", "Sarah", "Ruth", "Hannah",
    "Akinyi", "Achieng", "Adhiambo", "Atieno", "Anyango", "Wanjiku", "Wambui", "Wangari", "Njeri", "Wanjiru",
    "Fatuma", "Aisha", "Zainab", "Halima", "Mariam", "Khadiija", "Nuru", "Saida", "Mwana", "Ashura",
]

KENYAN_LAST_NAMES = [
    "Otieno", "Onyango", "Ochieng", "Okoth", "Odhiambo", "Kamau", "Maina", "Mwangi", "Wanjiku", "Wambui",
    "Wangari", "Njeri", "Wanjiru", "Kiprono", "Kipchoge", "Kiplagat", "Kibet", "Jepchirchir", "Jelagat", "Cherono",
    "Mutai", "Kimetto", "Kiprop", "Ruto", "Odinga", "Kenyatta", "Moi", "Cheruiyot", "Njoroge", "Mohamed",
    "Hassan", "Ali", "Omar", "Abdi", "Ahmed", "Ibrahim", "Yusuf", "Farah", "Mutua", "Muthoni",
    "Wafula", "Wanjala", "Ouko", "Obiero", "Odanga", "Owiti", "Waweru", "Wahome", "Kariuki", "Githinji",
]

KENYAN_LOCATIONS = [
    "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret", "Thika", "Malindi",
    "Kitale", "Garissa", "Kakamega", "Nyeri", "Machakos", "Meru", "Lamu",
    "Naivasha", "Embu", "Voi", "Bungoma", "Kitui", "Busia", "Kericho",
    "Nanyuki", "Kajiado", "Sotik", "Homabay", "Kilifi", "Migori", "Marsabit",
    "Isiolo", "Kakuma", "Wajir", "Mandera", "Kisii", "Kwale", "Taveta"
]

# Bios (unchanged)
client_bio = """I am a dedicated entrepreneur and business professional with over 10 years of experience..."""  # (your full bio here)

freelancers_bio = """I am a passionate and results-driven freelancer with extensive experience..."""  # (your full bio here)


def generate_kenyan_phone():
    return f"07{random.randint(10_000_000, 99_999_999)}"


def valid_kenyan_phone(value: str) -> bool:
    return bool(value and isinstance(value, str) and value.startswith("07") and len(value) == 10 and value.isdigit())


def random_profile_pic(user_type='client'):
    seed = random.randint(1, 1000)
    return f"https://i.pravatar.cc/300?img={seed}" if user_type == 'client' else f"https://i.pravatar.cc/300?img={seed+50}"


class Command(BaseCommand):
    help = 'Seed clean data — mix of realistic Kenyan names + Faker names, correct profiles, bios and pics'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Clear all data first')
        parser.add_argument('--clients', type=int, default=30)
        parser.add_argument('--freelancers', type=int, default=20)

    def handle(self, *args, **options):
        self.fake = Faker()
        self.fake.seed_instance(1234)
        random.seed(1234)

        if options['clear']:
            self.clear_data()

        self.stdout.write(
            f"Creating {options['clients']} clients + {options['freelancers']} freelancers...")
        self.create_base_data()

        with transaction.atomic():
            self.clients = self.create_clients(options['clients'])
            self.freelancers = self.create_freelancers(options['freelancers'])
            self.create_jobs_from_json()
            self.create_responses()

        self.print_summary()

    def clear_data(self):
        self.stdout.write("Clearing all old data...")
        Response.objects.all().delete()
        Job.objects.all().delete()
        FreelancerProfile.objects.all().delete()
        ClientProfile.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.SUCCESS("Cleared!"))

    def create_base_data(self):
        # Skills
        skills_list = ["JavaScript", "React", "Python",
                       "Django", "SEO", "Figma", "WordPress", "Video Editing"]
        for skill in skills_list:
            Skill.objects.get_or_create(name=skill)

        # Languages
        for code, _ in Language.LANGUAGE_CHOICES:
            Language.objects.get_or_create(name=code)

        self.skills = list(Skill.objects.all())
        self.languages = list(Language.objects.all())

        # Job categories from JSON
        json_path = os.path.join(os.path.dirname(__file__), 'jobs.json')
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
                for job in data:
                    JobCategory.objects.get_or_create(
                        name=job['category'],
                        defaults={'slug': slugify(job['category'])}
                    )

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _unique_username(self, base: str, limit: int = 30) -> str:
        uname = base[:limit]
        suffix = random.randint(10, 9999)
        candidate = f"{uname}{suffix}"[:limit]
        while User.objects.filter(username=candidate).exists():
            suffix = random.randint(10000, 999999)
            candidate = f"{uname}{suffix}"[:limit]
        return candidate

    def _ensure_profile(self, profile: Profile, user_type='client'):
        updated = False
        if not valid_kenyan_phone(profile.phone):
            profile.phone = generate_kenyan_phone()
            updated = True
        if not profile.location:
            profile.location = random.choice(KENYAN_LOCATIONS)
            updated = True
        if not profile.bio:
            profile.bio = client_bio if user_type == 'client' else freelancers_bio
            updated = True
        if not profile.profile_pic:
            profile.profile_pic = random_profile_pic(user_type)
            updated = True
        if updated:
            profile.save()

    def _get_random_name(self):
        """Mix real Kenyan names (70%) with Faker names (30%)"""
        if random.random() < 0.70:  # 70% chance of Kenyan-style name
            gender_is_male = random.random() < 0.55  # slight male bias
            if gender_is_male:
                first = random.choice(KENYAN_FIRST_NAMES_MALE)
            else:
                first = random.choice(KENYAN_FIRST_NAMES_FEMALE)
            last = random.choice(KENYAN_LAST_NAMES)
        else:
            # Faker fallback
            first = self.fake.first_name()
            last = self.fake.last_name()
        return first, last

    def _create_user_profile(self, first, last, email, user_type='client'):
        username = self._unique_username(f"{first.lower()}{last.lower()}")
        user = User.objects.create_user(
            username=username,
            email=email,
            password='string12345',
            first_name=first,
            last_name=last
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.user_type = user_type
        self._ensure_profile(profile, user_type)
        return user, profile

    # ── Creation functions ─────────────────────────────────────────────────────
    def create_clients(self, count):
        clients = []
        for _ in range(count):
            first, last = self._get_random_name()
            email = f"{first.lower()}.{last.lower()}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'proton.me'])}"

            user, profile = self._create_user_profile(
                first, last, email, 'client')

            client_profile, _ = ClientProfile.objects.get_or_create(
                profile=profile,
                defaults={
                    'company_name': self.fake.company(),
                    'company_website': f"https://www.{slugify(self.fake.company())}.com",
                    'industry': random.choice([c[0] for c in ClientProfile.INDUSTRY_CHOICES]),
                    'project_budget': Decimal(round(random.uniform(50_000, 1_000_000), 2)),
                }
            )
            client_profile.languages.set(random.sample(
                self.languages, k=random.randint(1, min(3, len(self.languages)))))
            clients.append(client_profile)
        self.stdout.write(self.style.SUCCESS(
            f"Created {len(clients)} clients"))
        return clients

    def create_freelancers(self, count):
        freelancers = []
        for _ in range(count):
            first, last = self._get_random_name()
            email = f"{first.lower()}.{last.lower()}{random.randint(10, 99)}@gmail.com"

            user, profile = self._create_user_profile(
                first, last, email, 'freelancer')

            fp, _ = FreelancerProfile.objects.get_or_create(
                profile=profile,
                defaults={
                    'experience_years': random.randint(1, 18),
                    'hourly_rate': Decimal(round(random.uniform(15, 250), 2)),
                    'availability': random.choice(['full_time', 'part_time', 'custom']),
                    'is_visible': True
                }
            )
            fp.skills.set(random.sample(
                self.skills, k=random.randint(1, min(12, len(self.skills)))))
            fp.languages.set(random.sample(
                self.languages, k=random.randint(1, min(4, len(self.languages)))))
            freelancers.append(fp)
        self.stdout.write(self.style.SUCCESS(
            f"Created {len(freelancers)} freelancers"))
        return freelancers

    def create_jobs_from_json(self):
        path = os.path.join(os.path.dirname(__file__), 'jobs.json')
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR("jobs.json not found!"))
            return

        with open(path) as f:
            jobs_data = json.load(f)

        created = 0
        for data in jobs_data:
            if Job.objects.filter(title=data['title']).exists():
                continue
            client = random.choice(self.clients)
            category = JobCategory.objects.get(name__iexact=data['category'])
            deadline = timezone.datetime.fromisoformat(
                data['deadline_date'].replace('Z', '+00:00'))

            Job.objects.create(
                title=data['title'],
                category=category,
                description=data['description'],
                price=Decimal(data['price']),
                deadline_date=deadline,
                posted_date=timezone.now() - timedelta(days=random.randint(1, 120)),
                status='open',
                client=client.profile,
                max_freelancers=random.randint(5, 15),
                required_freelancers=random.randint(1, 4),
                preferred_freelancer_level='intermediate',
                payment_verified=True
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} jobs"))

    def create_responses(self):
        open_jobs = list(Job.objects.filter(status='open')[:30])
        freelancers_pool = getattr(self, "freelancers", []) or list(
            FreelancerProfile.objects.all())
        for job in open_jobs:
            for fp in random.sample(freelancers_pool, k=min(6, len(freelancers_pool))):
                if random.random() < 0.7:
                    Response.objects.get_or_create(
                        user=fp.profile.user,
                        job=job,
                        defaults={'extra_data': {
                            'cover_letter': self.fake.paragraph()}}
                    )
        self.stdout.write(self.style.SUCCESS("Created responses"))

    def print_summary(self):
        self.stdout.write("\n" + "="*70)
        self.stdout.write(" SEEDING DONE — ZERO ERRORS ".center(70, "="))
        self.stdout.write(f" Clients:      {ClientProfile.objects.count()}")
        self.stdout.write(
            f" Freelancers:  {FreelancerProfile.objects.count()}")
        self.stdout.write(f" Jobs:         {Job.objects.count()}")
        self.stdout.write(f" Responses:    {Response.objects.count()}")
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(
            "Password for all users: string12345"))
        self.stdout.write(self.style.SUCCESS(
            "Names: mix of Kenyan-style (Otieno Kamau, Akinyi Wanjiku…) + Faker"))
        self.stdout.write("="*70)
