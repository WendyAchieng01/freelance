
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from accounts.models import FreelancerProfile
from core.models import Job, Response
from wallet.models import Rate
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed realistic job applications using the CURRENT platform rate (no manual input)"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Delete ALL existing applications first')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be created')
        parser.add_argument('--apply-rate', type=float, default=0.68,
                            help='Chance a freelancer applies to a suitable job (default: 68%)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear_first = options['clear']
        apply_rate = options['apply_rate']

        if clear_first:
            self.stdout.write("Clearing all existing applications...")
            Response.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared!"))

        # DYNAMIC PLATFORM RATE — pulled from your Rate model
        try:
            platform_rate = Rate.objects.latest('effective_from').rate_amount
            self.stdout.write(self.style.SUCCESS(
                f"Using current platform fee: {platform_rate}%"))
        except Rate.DoesNotExist:
            platform_rate = Decimal('8.00')
            self.stdout.write(self.style.WARNING(
                "No rate found → using default 8.00%"))

        freelancers = FreelancerProfile.objects.filter(
            profile__user__is_active=True,
            is_visible=True
        ).select_related('profile__user')

        jobs = Job.objects.filter(
            status='open',
            payment_verified=True
        ).prefetch_related('skills_required', 'responses')

        if not freelancers.exists() or not jobs.exists():
            self.stdout.write(self.style.ERROR(
                "Run seed_data + seed_payments_and_wallet first!"))
            return

        self.stdout.write(
            f"{freelancers.count()} freelancers → {jobs.count()} open jobs | Apply rate: {apply_rate:.0%}")

        cover_templates = [
            "Hi! I'd love to work on your {title}. I have {exp}+ years in {skills} and deliver clean, on-time work. My rate is competitive and I'm available immediately.",
            "Hello! Your project looks perfect for my skillset. I've done many {skills} projects with great feedback. Let's discuss how I can help!",
            "Hey! Saw your {title} post — this is exactly what I specialize in. {exp} years experience, strong portfolio, and ready to start.",
            "Greetings! As a {skills} expert with {exp}+ years, I'm confident I can deliver excellent results for you. Looking forward to collaborating!",
        ]

        created = 0
        for job in jobs:
            candidates = self.get_suitable_freelancers(job, freelancers)

            for fp in candidates:
                if job.responses.filter(user=fp.profile.user).exists():
                    continue
                if job.responses.count() >= job.max_freelancers:
                    continue
                if random.random() > apply_rate:
                    continue

                skills_str = ", ".join(s.name for s in fp.skills.all()[
                                       :3]) or "relevant skills"
                cover = random.choice(cover_templates).format(
                    title=job.title.lower(),
                    skills=skills_str,
                    exp=fp.experience_years or 3
                )

                # Use the REAL platform rate in proposed rate calculation
                base_rate = float(fp.hourly_rate)
                proposed_rate = round(
                    base_rate * random.uniform(0.92, 1.25), 2)

                extra_data = {
                    "cover_letter": cover,
                    "proposed_rate": proposed_rate,
                    # Real rate from DB
                    "platform_fee_percent": float(platform_rate),
                    "expected_duration_days": random.randint(3, 21),
                    "availability": fp.get_availability_display(),
                    "time_zone": random.choice(["EAT", "GMT", "EST", "PST", "UTC+3"]),
                }

                if dry_run:
                    self.stdout.write(
                        f"[DRY] {fp.profile.user.username} → \"{job.title[:45]}...\" | ${proposed_rate}/hr")
                    created += 1
                    continue

                Response.objects.create(
                    user=fp.profile.user,
                    job=job,
                    extra_data=extra_data,
                    status='submitted'
                )

                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Applied → {fp.profile.user.username:<20} → {job.title[:55]:<55} | ${proposed_rate}/hr"
                    )
                )

        self.stdout.write("\n" + "═" * 92)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f" DRY RUN: Would create {created} applications "))
        else:
            self.stdout.write(self.style.SUCCESS(
                f" SUCCESS: {created} applications created with REAL {platform_rate}% platform fee "))
        self.stdout.write("═" * 92)
        self.stdout.write(self.style.SUCCESS(
            "Applications seeded perfectly using live platform rate"))

    def get_suitable_freelancers(self, job, freelancers_qs):
        required = set(job.skills_required.values_list('id', flat=True))
        if not required:
            return list(freelancers_qs.order_by('?')[:25])

        matches = []
        others = []
        for fp in freelancers_qs:
            has_match = required.intersection(
                fp.skills.values_list('id', flat=True))
            (matches if has_match else others).append(fp)

        # Prioritize skill matches
        pool = matches or others
        return random.sample(pool, min(20, len(pool)))
