from decimal import Decimal
from django.db import transaction
from django.contrib.auth.models import User

from wallet.models import PaymentBatch, WalletTransaction, PaymentPeriod


@transaction.atomic
def create_payment_batch(
    *,
    admin_user: User,
    provider: str,
    period: PaymentPeriod
) -> PaymentBatch:
    """
    Create a PaymentBatch and attach eligible WalletTransactions.
    """

    txs = (
        WalletTransaction.objects
        .select_for_update()
        .filter(
            status="pending",
            batch__isnull=True,
            payment_period=period,
            payment_type=provider,
            job__status="completed",
        )
    )

    if not txs.exists():
        raise ValueError("No eligible transactions for this period")

    batch = PaymentBatch.objects.create(
        provider=provider,
        period=period,
        user=admin_user,
        status="pending",
    )

    total = Decimal("0.00")

    for tx in txs:
        tx.batch = batch
        tx.save(update_fields=["batch"])
        total += tx.amount or Decimal("0.00")

    batch.total_amount = total
    batch.save(update_fields=["total_amount"])

    return batch
