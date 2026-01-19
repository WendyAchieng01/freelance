from django.core.management.base import BaseCommand
from django.utils import timezone

from wallet.models import PaymentPeriod, PaymentBatch
from wallet.services.batch_discovery import auto_discover_batches
from wallet.services.payout_executor import execute_batch_payout


class Command(BaseCommand):
    help = "Run payouts for payment periods that have ended"

    def handle(self, *args, **kwargs):
        today = timezone.now().date()

        # Ensure batches exist
        auto_discover_batches()

        batches = PaymentBatch.objects.filter(
            status="pending",
            period__end_date__lt=today,
        )

        for batch in batches:
            self.stdout.write(
                f"Running payout for batch {batch.reference}"
            )
            execute_batch_payout(batch)
