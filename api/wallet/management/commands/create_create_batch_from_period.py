from django.core.management.base import BaseCommand
from wallet.models import PaymentPeriod, WalletTransaction, PaymentBatch
from decimal import Decimal


class Command(BaseCommand):
    help = "Create payment batch for a given period name (or id)"

    def add_arguments(self, parser):
        parser.add_argument('--period-id', type=int, help='PaymentPeriod id')
        parser.add_argument('--provider', type=str,
                            choices=['paystack', 'paypal'], default='paystack')

    def handle(self, *args, **options):
        period_id = options.get('period_id')
        provider = options.get('provider')
        period = PaymentPeriod.objects.get(pk=period_id)
        pending = WalletTransaction.objects.filter(
            payment_period=period, status='pending', batch__isnull=True)
        if not pending.exists():
            self.stdout.write("No pending transactions")
            return
        batch = PaymentBatch.objects.create(
            provider=provider, period=period, total_amount=Decimal(0))
        total = 0
        for tx in pending:
            tx.batch = batch
            tx.save(update_fields=['batch'])
            total += tx.amount or 0
        batch.total_amount = total
        batch.save(update_fields=['total_amount'])
        self.stdout.write(
            f"Created batch {batch.reference} with {pending.count()} txs")
