from django.db import transaction
from celery import shared_task
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

    if batch.provider == "paystack":
        PayoutManager.execute_batch(batch)
        return
    
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



@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={"max_retries": 5})
def process_payout_batch(self, batch_id):
    from api.wallet.gateways import get_payout_gateway

    batch = PaymentBatch.objects.select_for_update().get(id=batch_id)

    if batch.status != "created":
        return

    txs = list(
        WalletTransaction.objects.select_for_update().filter(
            batch=batch,
            status=WalletTransaction.Status.PENDING,
        )
    )

    if not txs:
        return

    gateway = get_payout_gateway(batch.provider)

    with transaction.atomic():
        batch.status = "sending"
        batch.save(update_fields=["status"])

        result = gateway.send_bulk(batch, txs)

        batch.provider_reference = result["reference"]
        batch.status = "sent"
        batch.save(update_fields=["provider_reference", "status"])

        ref_map = {i["tx_id"]: i["provider_ref"] for i in result["items"]}

        for tx in txs:
            tx.status = WalletTransaction.Status.IN_PROGRESS
            tx.provider_reference = ref_map.get(tx.id)
            tx.save(update_fields=["status", "provider_reference"])
