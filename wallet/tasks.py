import logging
from wallet.payouts.manager import PayoutManager
from wallet.models import PaymentBatch, PayoutLog, WalletTransaction



def retry_failed_payouts():
    """Automatically retries failed payouts."""
    failed = WalletTransaction.objects.filter(status="failed")

    for tx in failed:
        try:
            ok = PayoutManager.execute_payout(tx)
            if ok:
                PayoutLog.objects.create(
                    provider=tx.batch.provider,
                    wallet_tx=tx,
                    request_payload={"retry": True},
                    response_payload={"status": "success"}
                )
        except Exception as e:
            PayoutLog.objects.create(
                provider=tx.batch.provider,
                wallet_tx=tx,
                request_payload={"retry": True},
                response_payload={"error": str(e)}
            )


logger = logging.getLogger(__name__)


def process_batch_payment_v2(batch_id):
    """
    Processes a payment batch by iterating through its transactions
    and calling the appropriate payout provider.
    """
    try:
        batch = PaymentBatch.objects.get(id=batch_id)
    except PaymentBatch.DoesNotExist:
        logger.error(f"PaymentBatch with ID {batch_id} not found.")
        return

    if batch.status not in ['pending', 'partial']:
        logger.warning(
            f"Batch {batch.id} is already being processed or is completed. Status: {batch.status}")
        return

    batch.status = 'processing'
    batch.save(update_fields=['status'])

    transactions = batch.transactions.filter(status='pending')
    successful_payouts = 0

    for tx in transactions:
        try:
            # Use PayoutManager to handle the specific gateway logic
            success = PayoutManager.execute_payout(tx)
            if success:
                tx.status = 'completed'
                tx.completed = True
                tx.save(update_fields=['status', 'completed'])
                successful_payouts += 1
                PayoutLog.objects.create(
                    batch=batch,
                    wallet_transaction=tx,
                    provider=batch.provider,
                    endpoint="batch_payout_v2",
                    status_code=200,
                    response_payload={"status": "success",
                                      "message": "Payout completed via batch v2."}
                )
            else:
                # If execute_payout returns False, it's a controlled failure
                tx.status = 'failed'
                tx.save(update_fields=['status'])
                # The PayoutManager should have created a PayoutLog with details

        except Exception as e:
            logger.error(
                f"Error processing payout for WalletTransaction {tx.id} in batch {batch.id}: {e}")
            tx.status = 'failed'
            tx.save(update_fields=['status'])
            PayoutLog.objects.create(
                batch=batch,
                wallet_transaction=tx,
                provider=batch.provider,
                endpoint="batch_payout_v2",
                status_code=500,
                error=str(e),
                response_payload={"status": "error",
                                  "message": "An unexpected error occurred."}
            )

    # Update batch status based on the outcome
    if successful_payouts == transactions.count():
        batch.status = 'completed'
    elif successful_payouts > 0:
        batch.status = 'partial'
    else:
        batch.status = 'failed'

    batch.save(update_fields=['status'])
    logger.info(
        f"Batch {batch.id} processing finished with status: {batch.status}")
