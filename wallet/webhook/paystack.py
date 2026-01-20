from wallet.models import WalletTransaction, PayoutLog
from django.utils import timezone
import json
import logging
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from api.wallet.gateways import get_payout_gateway
from wallet.models import WalletTransaction, PaymentBatch, PayoutLog
from wallet.services.batch_finalizer import finalize_batch_status

logger = logging.getLogger(__name__)


logger.info("Webhook hit at %s", timezone.now())


@csrf_exempt
def paystack_webhook(request):
    logger.info("=== PAYSTACK WEBHOOK HIT === Time: %s", timezone.now())
    logger.info("Headers: %s", dict(request.headers))
    logger.info("Raw body: %s", request.body.decode('utf-8', errors='replace'))
    
    gateway = get_payout_gateway("paystack")

    # Verify signature first
    if not gateway.verify_webhook(request.headers, request.body):
        logger.warning("Invalid Paystack webhook signature")
        return HttpResponseBadRequest("Invalid signature")

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        return HttpResponseBadRequest("Invalid JSON")

    event = payload.get("event")
    data = payload.get("data", {})

    logger.info("Paystack webhook received | event=%s | reference=%s",
                event, data.get("reference"))

    if event in ("transfer.success", "transfer.failed", "transfer.reversed"):
        _handle_transfer_event(event, data)

    return JsonResponse({"status": "ok"})


def _handle_transfer_event(event: str, data: dict):
    transfer_code = data.get("transfer_code")
    print(data)
    if not transfer_code:
        logger.warning("Webhook missing transfer_code")
        return

    with transaction.atomic():
        try:
            tx = WalletTransaction.objects.select_for_update().select_related(
                "batch", "user", "user__profile"
            ).get(provider_reference=transfer_code)
        except WalletTransaction.DoesNotExist:
            logger.error("Tx not found for transfer_code=%s", transfer_code)
            return

        if tx.status in ("completed", "failed"):
            logger.info("Webhook duplicate tx=%s", tx.id)
            return

        if event == "transfer.success":
            tx.status = "completed"
            tx.completed = True
        else:
            tx.status = "failed"

        tx.payment_type = "paystack"
        tx.transaction_id = transfer_code

        tx.extra_data.update({
            "webhook_event": event,
            "recipient": data.get("recipient"),
            "amount": data.get("amount"),
            "paid_at": data.get("paid_at"),
            "raw_status": data.get("status"),
        })

        tx.save(update_fields=[
            "status",
            "completed",
            "payment_type",
            "transaction_id",
            "extra_data",
        ])

        PayoutLog.objects.create(
            wallet_transaction=tx,
            batch=tx.batch,
            provider="paystack",
            endpoint=f"webhook:{event}",
            response_payload=data,
            status_code=200,
            processed=True,
            idempotency_key=transfer_code,
        )

        if tx.batch:
            finalize_batch_status(tx.batch)
