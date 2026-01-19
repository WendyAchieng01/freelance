import logging
from django.db import transaction
from wallet.models import WalletTransaction, PaymentBatch
from accounts.models import Profile


logger = logging.getLogger(__name__)


def find_transfer_by_recipient(recipient, transfers):
    """
    Search for a transfer dictionary by recipient in the nested transfers dictionary.
    
    Args:
        recipient (str): The recipient value to search for.
        transfers (dict): The nested dictionary containing transfer data.
        
    Returns:
        dict or None: The dictionary for the matching recipient, or None if not found.
    """
    for transfer in transfers.get("data", []):
        if transfer.get("recipient") == recipient:
            return transfer
    return None


def reconcile_paystack_batch(batch: PaymentBatch, paystack_response: dict):
    logger.info(
        "[PaystackReconcile] Starting | batch_id=%s",
        batch.id
    )

    qs = WalletTransaction.objects.select_related(
        "user", "user__profile"
    ).filter(batch=batch)

    if not qs.exists():
        logger.error(
            "[PaystackReconcile] No transactions found | batch_id=%s",
            batch.id
        )
        return {
            "updated": 0,
            "skipped": 0,
            "errors": ["No WalletTransactions found for this batch."]
        }

    updated = 0
    skipped = 0
    errors = []

    users = set(qs.values_list("user_id", flat=True))

    with transaction.atomic():
        for user_id in users:
            user_txs = qs.filter(user_id=user_id)
            user = user_txs.first().user
            profile = getattr(user, "profile", None)

            if not profile or not profile.paystack_recipient:
                msg = f"User {user_id} missing paystack_recipient"
                logger.warning("[PaystackReconcile] %s", msg)
                skipped += user_txs.count()
                errors.append(msg)
                continue

            transfer = find_transfer_by_recipient(
                profile.paystack_recipient,
                paystack_response
            )

            if not transfer:
                msg = f"No transfer for recipient {profile.paystack_recipient}"
                logger.warning("[PaystackReconcile] %s", msg)
                skipped += user_txs.count()
                errors.append(msg)
                continue

            for tx in user_txs:
                tx.transaction_type = "payment_received"
                tx.status = "completed"
                tx.completed = True

                tx.provider_reference = transfer.get("transfer_code")
                tx.extra_data = transfer

                tx.save(update_fields=[
                    "transaction_type",
                    "status",
                    "completed",
                    "provider_reference",
                    "extra_data",
                ])

                updated += 1

            logger.info(
                "[PaystackReconcile] User reconciled | user_id=%s tx_count=%s",
                user_id,
                user_txs.count()
            )

        # Batch status
        if updated and skipped == 0:
            batch.status = "completed"
        elif updated and skipped > 0:
            batch.status = "partial"
        else:
            batch.status = "failed"

        batch.provider_reference = paystack_response.get(
            "meta", {}).get("batch_code")

        batch.save(update_fields=["status", "provider_reference"])

        logger.info(
            "[PaystackReconcile] Batch finalized | batch_id=%s status=%s updated=%s skipped=%s",
            batch.id,
            batch.status,
            updated,
            skipped
        )

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
