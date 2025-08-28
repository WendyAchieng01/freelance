from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from wallet.models import PaymentPeriod


class Command(BaseCommand):
    help = "Generate upcoming payment periods (weekly or monthly)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--weeks', type=int, default=4,
            help='Number of weekly payment periods to generate'
        )

    def handle(self, *args, **options):
        weeks = options['weeks']
        today = timezone.now().date()
        start_date = today

        for i in range(weeks):
            end_date = start_date + timedelta(days=6)
            name = f"Week of {start_date.strftime('%Y-%m-%d')}"
            period, created = PaymentPeriod.objects.get_or_create(
                start_date=start_date,
                end_date=end_date,
                defaults={'name': name}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {period}"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Already exists: {period}"))

            start_date = end_date + timedelta(days=1)
