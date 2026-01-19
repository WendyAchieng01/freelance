from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction

from wallet.models import WalletTransaction, PaymentBatch

User = get_user_model()


@transaction.atomic
def auto_discover_batches(provider="paystack"):
    """
    Create missing PaymentBatch records for pending transactions.
    Safe to run multiple times (idempotent).
    """

    system_user = (
        User.objects.filter(is_superuser=True).first()
        or User.objects.filter(is_staff=True).first()
    )

    qs = (
        WalletTransaction.objects
        .select_for_update()
        .filter(
            status="pending",
            batch__isnull=True,
            payment_period__isnull=False,
            job__status="completed",
        )
    )

    period_ids = qs.values_list("payment_period_id", flat=True).distinct()

    for period_id in period_ids:
        if PaymentBatch.objects.filter(
            period_id=period_id,
            provider=provider,
        ).exists():
            continue

        batch = PaymentBatch.objects.create(
            provider=provider,
            period_id=period_id,
            user=system_user,
            status="pending",
        )

        txs = qs.filter(payment_period_id=period_id)

        total = Decimal("0.00")
        for tx in txs:
            tx.batch = batch
            tx.save(update_fields=["batch"])
            total += tx.amount or Decimal("0.00")

        batch.total_amount = total
        batch.save(update_fields=["total_amount"])
