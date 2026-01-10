from decimal import Decimal
from django.db import transaction
from collections import defaultdict

from wallet.models import WalletTransaction, PaymentBatch, PaymentPeriod


def create_batches_for_period(period: PaymentPeriod = None):
    """
    Create PaymentBatch objects grouped by provider for WalletTransactions that:
      - are attached to Jobs with status 'completed'
      - are status 'pending'
      - are not yet assigned to a batch
      - (optionally) belong to the provided payment period
    Returns a list of created PaymentBatch instances.
    """
    qs = WalletTransaction.objects.filter(
        job__status='completed',
        status='pending',
        batch__isnull=True
    ).select_related('user__profile', 'job', 'payment_period', 'rate')

    if period:
        qs = qs.filter(payment_period=period)

    txs_by_provider = defaultdict(list)
    for tx in qs:
        provider = (tx.payment_type or 'paystack').lower()
        txs_by_provider[provider].append(tx)

    created_batches = []

    for provider, txs in txs_by_provider.items():
        with transaction.atomic():
            batch = PaymentBatch.objects.create(
                provider=provider,
                period=period,
                total_amount=Decimal('0.00'),
                status='pending'
            )

            total = Decimal('0.00')
            for tx in txs:
                # Ensure amounts are computed on the tx (idempotent)
                try:
                    tx.compute_amounts()
                except Exception:
                    # If compute fails, mark tx failed and skip
                    tx.status = 'failed'
                    tx.extra_data = {"error": "compute_amounts_failed"}
                    tx.save(update_fields=['status', 'extra_data'])
                    continue

                tx.batch = batch
                # Save only relevant fields to avoid overriding unrelated updates
                tx.save(update_fields=[
                        'batch', 'gross_amount', 'fee_amount', 'amount'])
                total += tx.amount or Decimal('0.00')

            # update batch total
            batch.total_amount = total
            batch.save(update_fields=['total_amount'])
            created_batches.append(batch)

    return created_batches
