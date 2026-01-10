import time
from django.db.models import Q
from django.db import transaction
from wallet.models import PaymentBatch, WalletTransaction
from api.wallet.gateways.paystack import PaystackGateway
from api.wallet.gateways.paypal import PayPalGateway
import logging

logger = logging.getLogger(__name__)

GATEWAYS = {
    "paystack": PaystackGateway,
    "paypal": PayPalGateway,
}


def process_batch(batch_id: str, dry_run: bool = False):
    try:
        batch = PaymentBatch.objects.prefetch_related(
            'transactions__user__profile').get(id=batch_id)
    except PaymentBatch.DoesNotExist:
        logger.error("Batch %s not found", batch_id)
        return {"error": "batch not found"}

    batch.status = "processing"
    batch.save(update_fields=['status'])

    provider = (batch.provider or "").lower()
    gateway_cls = GATEWAYS.get(provider)
    if not gateway_cls:
        batch.status = "failed"
        batch.note = f"No gateway configured for provider {batch.provider}"
        batch.save(update_fields=['status', 'note'])
        return {"error": "no gateway"}

    gateway = gateway_cls()
    all_success = True
    any_processed = False

    txs = batch.transactions.filter(status='pending').select_related(
        'user__profile').order_by('timestamp')

    for tx in txs:
        any_processed = True
        try:
            with transaction.atomic():
                tx_for_update = WalletTransaction.objects.select_for_update().get(pk=tx.pk)

                if tx_for_update.completed or tx_for_update.status == 'completed':
                    continue

                if not getattr(tx_for_update.user, "email", None):
                    tx_for_update.status = "failed"
                    tx_for_update.extra_data = {"error": "missing_user_email"}
                    tx_for_update.save(update_fields=['status', 'extra_data'])
                    all_success = False
                    continue

                profile = getattr(tx_for_update.user, "profile", None)
                if not profile or not getattr(profile, "pay_id", None):
                    tx_for_update.status = "failed"
                    tx_for_update.extra_data = {"error": "missing_pay_id"}
                    tx_for_update.save(update_fields=['status', 'extra_data'])
                    all_success = False
                    continue

                if dry_run:
                    tx_for_update.status = 'in_progress'
                    tx_for_update.save(update_fields=['status'])
                    continue

                idempotency_key = f"batch-{batch.reference}-tx-{tx_for_update.id}"
                attempt = 0
                max_attempts = 4
                success = False
                last_err = None

                while attempt < max_attempts and not success:
                    attempt += 1
                    try:
                        res = gateway.payout(
                            tx_for_update, idempotency_key=idempotency_key)
                    except Exception as exc:
                        logger.exception(
                            "Gateway raised exception for tx %s attempt %s", tx_for_update.id, attempt)
                        res = {"success": False, "provider_ref": None,
                               "raw": None, "error": str(exc)}

                    if res.get('success'):
                        tx_for_update.status = 'completed'
                        tx_for_update.transaction_id = res.get('provider_ref')
                        tx_for_update.extra_data = res.get('raw') or {}
                        tx_for_update.completed = True
                        tx_for_update.save(
                            update_fields=['status', 'transaction_id', 'extra_data', 'completed'])
                        success = True
                        break
                    else:
                        last_err = res.get('error') or 'unknown_error'
                        tx_for_update.status = 'in_progress' if attempt < max_attempts else 'failed'
                        tx_for_update.extra_data = {
                            "attempts": attempt, "last_error": last_err, "raw": res.get('raw')}
                        tx_for_update.save(
                            update_fields=['status', 'extra_data'])
                        if attempt < max_attempts:
                            time.sleep(min(2 ** attempt, 30))

                if not success:
                    all_success = False

        except Exception as exc:
            logger.exception(
                "Unexpected error processing tx %s in batch %s: %s", tx.id, batch_id, exc)
            all_success = False

    if not any_processed:
        batch.status = "failed"
        batch.note = "No eligible transactions to process"
    else:
        succeeded = batch.transactions.filter(status='completed').count()
        failed = batch.transactions.filter(
            Q(status='failed') | Q(completed=False)).count()
        if succeeded > 0 and failed > 0:
            batch.status = "partial"
        elif succeeded == 0 and failed > 0:
            batch.status = "failed"
        else:
            batch.status = "completed"

    batch.save(update_fields=['status', 'note'])
    return {"batch_id": str(batch.id), "status": batch.status}
