from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date
from analytics.models import DailyAnalytics
import random


class Command(BaseCommand):
    help = "Populate historical analytics. Use --months=N to generate synthetic data for the past N months."

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=None,
            help="Generate random synthetic analytics for the past N months.",
        )

    def handle(self, *args, **options):
        months = options.get("months")

        if months:
            return self.generate_random(months)
        else:
            return self.populate_real_365()


    def populate_real_365(self):
        self.stdout.write("Running REAL historical analytics (365 days)...")

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)

        total_days = (end_date - start_date).days + 1
        processed = 0

        current = start_date
        while current <= end_date:
            fake_today = timezone.make_aware(
                timezone.datetime(current.year, current.month,
                                  current.day, 12, 0)
            )
            original_now = timezone.now
            timezone.now = lambda: fake_today

            try:
                DailyAnalytics.update_today()
                processed += 1
                if processed % 50 == 0:
                    self.stdout.write(
                        f"Processed {processed}/{total_days} days...")
            finally:
                timezone.now = original_now

            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"SUCCESS: Populated REAL analytics for {processed} days!"
        ))


    def generate_random(self, months):
        self.stdout.write(self.style.WARNING(
            f"Generating RANDOM analytics for the past {months} months..."
        ))

        end = timezone.now().date()
        start = end - timedelta(days=months * 30)

        current = start
        total_days = (end - start).days + 1
        processed = 0

        while current <= end:
            # Skip if data for this date already exists
            obj, created = DailyAnalytics.objects.get_or_create(date=current)

            # Generate random but consistent values
            obj.new_users = random.randint(5, 50)
            obj.new_freelancers = random.randint(1, 20)
            obj.new_clients = random.randint(1, 20)

            obj.new_jobs = random.randint(3, 30)
            obj.new_applications = random.randint(10, 100)
            obj.new_hires = random.randint(0, obj.new_jobs)

            revenue = random.uniform(1000, 10000)
            payouts = revenue * random.uniform(0.6, 0.95)

            obj.revenue = round(revenue, 2)
            obj.payouts = round(payouts, 2)
            obj.platform_fees = obj.revenue - obj.payouts

            obj.save()

            processed += 1
            if processed % 50 == 0:
                self.stdout.write(
                    f"Generated {processed}/{total_days} days...")

            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"SUCCESS: Generated RANDOM analytics for {processed} days!"
        ))
        self.stdout.write(self.style.SUCCESS(
            "Charts should now look like a venture-funded Silicon Valley dashboard 🚀"
        ))
