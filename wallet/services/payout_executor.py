from django.db import transaction
from wallet.models import PaymentBatch,PayoutLog
from api.wallet.gateways import get_payout_gateway
import logging

logger = logging.getLogger(__name__)


def execute_batch_payout(batch: PaymentBatch):
    gateway = get_payout_gateway(batch.provider)

    # ---- PRE-FLIGHT LOCK ----
    with transaction.atomic():
        batch = PaymentBatch.objects.select_for_update().get(id=batch.id)

        if batch.status != "pending":
            raise RuntimeError("Batch already processed")

        tx_ids = list(
            batch.transactions
            .select_for_update()
            .filter(status="pending")
            .values_list("id", flat=True)
        )

        if not tx_ids:
            raise RuntimeError("No pending transactions in batch")

    # ---- EXTERNAL CALL (NO TRANSACTION) ----
    result = gateway.bulk_payout_batch(batch)

    if not result.get("success"):
        with transaction.atomic():
            batch.status = "failed"
            batch.save(update_fields=["status"])
        raise RuntimeError(result.get("error"))


    # ---- COMMIT SUCCESS STATE ----
    with transaction.atomic():
        batch.provider_reference = result["bulk_code"]
        batch.status = "processing"
        batch.save(update_fields=["provider_reference", "status"])

        batch.transactions.filter(id__in=tx_ids).update(status="in_progress")

    # CREATE PAYOULOG
    PayoutLog.objects.create(
        provider="paystack",
        endpoint="bulk_payout",
        batch=batch,
        response_payload=result.get("raw"),
        status_code=200,
        processed=False,
    )


    logger.info(
        "Batch payout started batch=%s provider_ref=%s",
        batch.reference,
        batch.provider_reference
    )

    return result
