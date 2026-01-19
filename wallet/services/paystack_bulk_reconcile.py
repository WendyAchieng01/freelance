from django.db import transaction
from wallet.models import WalletTransaction, PaymentBatch
from accounts.models import Profile


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
    """
    Reconcile a Paystack bulk transfer response against a PaymentBatch.

    Args:
        batch (PaymentBatch): The batch being reconciled.
        paystack_response (dict): Full response from Paystack bulk transfer list.
    """

    # All wallet transactions in this batch
    qs = WalletTransaction.objects.select_related(
        "user", "user__profile"
    ).filter(batch=batch)

    if not qs.exists():
        return {
            "updated": 0,
            "skipped": 0,
            "errors": ["No WalletTransactions found for this batch."]
        }

    updated = 0
    skipped = 0
    errors = []

    # Group by user
    users = set(qs.values_list("user_id", flat=True))

    with transaction.atomic():
        for user_id in users:
            user_txs = qs.filter(user_id=user_id)

            profile = getattr(user_txs.first().user, "profile", None)
            if not profile or not profile.paystack_recipient:
                skipped += user_txs.count()
                errors.append(f"User {user_id} has no paystack_recipient")
                continue

            transfer = find_transfer_by_recipient(
                profile.paystack_recipient,
                paystack_response
            )

            if not transfer:
                skipped += user_txs.count()
                errors.append(
                    f"No transfer found for recipient {profile.paystack_recipient}"
                )
                continue

            # Update all that user's transactions in this batch
            for tx in user_txs:
                tx.transaction_type = "payment_received"
                tx.transaction_id = transfer.get("transfer_code")
                tx.status = "completed"
                tx.completed = True
                tx.extra_data = transfer
                tx.save(update_fields=[
                    "transaction_type",
                    "transaction_id",
                    "status",
                    "completed",
                    "extra_data",
                ])
                updated += 1

        # Optionally update batch status
        if updated and skipped == 0:
            batch.status = "completed"
        elif updated and skipped > 0:
            batch.status = "partial"
        else:
            batch.status = "failed"

        batch.provider_reference = paystack_response.get(
            "meta", {}).get("batch_code")
        batch.save(update_fields=["status", "provider_reference"])

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
