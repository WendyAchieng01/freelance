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

from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from core.models import Job, JobCategory, Response

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed clean data — real usernames, correct profiles, no errors'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Clear all data first')
        parser.add_argument('--clients', type=int, default=30)
        parser.add_argument('--freelancers', type=int, default=20)

    def handle(self, *args, **options):
        self.fake = Faker()
        self.fake.seed_instance(1234)

        if options['clear']:
            self.clear_data()

        self.stdout.write(
            f"Creating {options['clients']} clients + {options['freelancers']} freelancers...")
        self.create_base_data()

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
        # Skills (minimal set — add more if needed)
        for name in ["JavaScript", "React", "Python", "Django", "SEO", "Figma", "WordPress", "Video Editing"]:
            Skill.objects.get_or_create(name=name)

        # Languages
        for code, _ in Language.LANGUAGE_CHOICES:
            Language.objects.get_or_create(name=code)

        self.skills = list(Skill.objects.all())
        self.languages = list(Language.objects.all())

        # Categories from jobs.json
        json_path = os.path.join(os.path.dirname(__file__), 'jobs.json')
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
                for job in data:
                    JobCategory.objects.get_or_create(
                        name=job['category'],
                        defaults={'slug': slugify(job['category'])}
                    )

    def create_clients(self, count):
        clients = []
        for _ in range(count):
            first = self.fake.first_name()
            last = self.fake.last_name()
            username = f"{first.lower()}{last.lower()}{random.randint(10, 999)}"[
                :30]
            email = f"{first.lower()}.{last.lower()}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'proton.me'])}"

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='string12345',
                first_name=first,
                last_name=last
            )

            # Create or get Profile
            profile, _ = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': self.fake.phone_number()[:20],
                    'location': f"{self.fake.city()}, {self.fake.country()}",
                    'bio': self.fake.paragraph(nb_sentences=3),
                    'pay_id': random.choice(['M-Pesa', 'Binance']),
                    'email_verified': True,
                }
            )

            # 🔥 ALWAYS update user_type
            profile.user_type = "client"
            profile.save(update_fields=["user_type"])

            # Now safely create ClientProfile
            client_profile, _ = ClientProfile.objects.get_or_create(
                profile=profile,
                defaults={
                    'company_name': self.fake.company(),
                    'company_website': f"https://www.{slugify(self.fake.company()).replace('-', '')}.com",
                    'industry': random.choice([c[0] for c in ClientProfile.INDUSTRY_CHOICES]),
                    'project_budget': Decimal(round(random.uniform(50000, 1000000), 2)),
                }
            )
            client_profile.languages.set(
                random.sample(self.languages, k=random.randint(1, 3))
            )
            clients.append(client_profile)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(clients)} clients with clean usernames"))
        return clients

    def create_freelancers(self, count):
        freelancers = []
        for _ in range(count):
            first = self.fake.first_name()
            last = self.fake.last_name()
            username = f"{first.lower()}{last.lower()}{random.randint(1, 999)}"[
                :30]
            email = f"{first.lower()}.{last.lower()}{random.randint(10, 99)}@gmail.com"

            user = User.objects.create_user(
                username=username,
                email=email,
                password='string12345',
                first_name=first,
                last_name=last
            )

            profile, _ = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': self.fake.phone_number()[:20],
                    'location': f"{self.fake.city()}, {self.fake.country()}",
                    'bio': self.fake.paragraph(nb_sentences=5),
                    'pay_id': random.choice(['M-Pesa', 'Binance']),
                    'email_verified': True,
                }
            )

            # 🔥 ALWAYS update user_type
            profile.user_type = "freelancer"
            profile.save(update_fields=["user_type"])

            fp, _ = FreelancerProfile.objects.get_or_create(
                profile=profile,
                defaults={
                    'experience_years': random.randint(1, 18),
                    'hourly_rate': Decimal(round(random.uniform(15, 250), 2)),
                    'availability': random.choice(['full_time', 'part_time', 'custom']),
                    'is_visible': True,
                }
            )
            fp.skills.set(random.sample(self.skills, k=random.randint(6, 12)))
            fp.languages.set(
                random.sample(self.languages, k=random.randint(1, 4))
            )
            freelancers.append(fp)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(freelancers)} freelancers with clean usernames"))
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
                data['deadline_date'].replace('Z', '+00:00')
            )

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
        for job in Job.objects.filter(status='open')[:30]:
            for fp in random.sample(self.freelancers, k=min(6, len(self.freelancers))):
                if random.random() < 0.7:
                    Response.objects.get_or_create(
                        user=fp.profile.user,
                        job=job,
                        defaults={
                            'extra_data': {
                                'cover_letter': self.fake.paragraph()
                            }
                        }
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
            "Clean usernames: johnsmith84, emilyjones27, etc."))
        self.stdout.write("="*70)
