from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction

from wallet.models import WalletTransaction, PaymentBatch

User = get_user_model()


@transaction.atomic
def auto_discover_batches(provider="paystack"):
    system_user = (
        User.objects.filter(is_superuser=True).first()
        or User.objects.filter(is_staff=True).first()
    )

    base_qs = (
        WalletTransaction.objects
        .select_for_update()
        .filter(
            status="pending",
            batch__isnull=True,
            payment_period__isnull=False,
            job__status="completed",
        )
    )

    period_ids = base_qs.values_list("payment_period_id", flat=True).distinct()

    for period_id in period_ids:
        # Find the most recent batch for this period/provider
        last_batch = (
            PaymentBatch.objects
            .select_for_update()
            .filter(period_id=period_id, provider=provider)
            .order_by("-created_at")
            .first()
        )

        # Decide whether we reuse or create a new one
        if last_batch and last_batch.provider_reference and last_batch.status == "completed":
            # Period already paid → create a new "late" batch
            batch = PaymentBatch.objects.create(
                provider=provider,
                period_id=period_id,
                user=system_user,
                status="late",
                note="Late jobs completed after initial batch was paid.",
                total_amount=Decimal("0.00"),
            )
        else:
            # Reuse existing open batch or create a normal one
            batch = last_batch
            if not batch:
                batch = PaymentBatch.objects.create(
                    provider=provider,
                    period_id=period_id,
                    user=system_user,
                    status="pending",
                    total_amount=Decimal("0.00"),
                )

        txs = (
            WalletTransaction.objects
            .select_for_update()
            .filter(
                status="pending",
                batch__isnull=True,
                payment_period_id=period_id,
                job__status="completed",
            )
        )

        if not txs.exists():
            continue

        total = batch.total_amount or Decimal("0.00")

        for tx in txs:
            tx.batch = batch
            tx.save(update_fields=["batch"])
            total += tx.amount or Decimal("0.00")

        batch.total_amount = total
        batch.save(update_fields=["total_amount"])
