from decimal import Decimal
from django.db import models
from django.db import transaction
from wallet.models import PaymentBatch,WalletTransaction

import logging

logger = logging.getLogger(__name__)


def finalize_batch_status(batch: PaymentBatch) -> None:
    """
    Checks current state of transactions in the batch and updates batch status.
    Call this after every individual tx update (from webhook).
    """
    if not batch:
        return

    with transaction.atomic():
        # Lock the batch
        batch = PaymentBatch.objects.select_for_update().get(pk=batch.pk)

        # Avoid re-processing completed batches
        if batch.status in ("completed", "failed"):
            return

        qs = WalletTransaction.objects.filter(batch=batch)

        total_tx = qs.count()
        if total_tx == 0:
            return

        pending = qs.filter(status="pending").count()
        completed = qs.filter(status="completed").count()
        failed = qs.filter(status__in=["failed", "cancelled"]).count()

        # Update batch status
        if pending == 0:
            if failed == 0:
                batch.status = "completed"
                logger.info("Batch %s fully completed", batch.reference)
            elif completed > 0:
                batch.status = "partial"
                logger.warning("Batch %s partial success (completed=%d, failed=%d)",
                                batch.reference, completed, failed)
            else:
                batch.status = "failed"
                logger.error("Batch %s all failed", batch.reference)

        else:
            # Still waiting for some transfers
            batch.status = "processing"

        # update total_amount if not already set
        if batch.total_amount == Decimal("0.00"):
            batch.total_amount = qs.aggregate(
                total=models.Sum("amount")
            )["total"] or Decimal("0.00")

        # store the batch reference from Paystack if available

        batch.save(update_fields=["status", "total_amount"])

        logger.info("Batch %s finalized to status=%s (pending=%d, completed=%d, failed=%d)",
                    batch.reference, batch.status, pending, completed, failed)
