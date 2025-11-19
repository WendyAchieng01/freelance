# analytics/management/commands/populate_historical_analytics.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from analytics.models import DailyAnalytics


class Command(BaseCommand):
    help = "Populate historical analytics for the last 365 days (WORKS 100%)"

    def handle(self, *args, **options):
        self.stdout.write("Starting historical analytics population...")

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)

        total_days = (end_date - start_date).days + 1
        processed = 0

        current = start_date
        while current <= end_date:
            # Fake "today" by monkey-patching timezone.now
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
                timezone.now = original_now  # Always restore

            current += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(
                f"SUCCESS: Populated analytics for {processed} days!")
        )
        self.stdout.write(self.style.SUCCESS(
            "Your dashboard now looks like a $100M platform"))
