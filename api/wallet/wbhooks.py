import json
from django.conf import settings
from wallet.models import PayoutLog
from wallet.models import WalletTransaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.wallet.gateways.paypal import PayPalGateway
from api.wallet.gateways.paystack import PaystackGateway


paystack_gateway = PaystackGateway()
paypal_gateway = PayPalGateway()


@csrf_exempt
@require_POST
def paystack_webhook(request):
    body = request.body
    headers = request.headers
    try:
        data = json.loads(body)
    except Exception:
        data = None

    # verify signature
    if not paystack_gateway.verify_webhook(headers, body):
        return HttpResponse(status=400)

    # handle event types (transfer.success, transfer.failed, etc.)
    event = data.get("event") if isinstance(data, dict) else None

    #  find wallet transaction by provider reference
    ref = None
    if isinstance(data, dict):
        ref = data.get("data", {}).get("reference") or data.get(
            "data", {}).get("transfer_code")

    if ref:
        # find the tx and update
        tx_qs = WalletTransaction.objects.filter(transaction_id=ref)
        if tx_qs.exists():
            tx = tx_qs.first()
            # update status depending on event
            if event in ("transfer.success", "transfer.completed", "transfer.completed"):
                tx.status = "completed"
                tx.completed = True
                tx.extra_data = {"webhook": data}
                tx.save(update_fields=['status', 'completed', 'extra_data'])
            elif event in ("transfer.failed", "transfer.reversed"):
                tx.status = "failed"
                tx.extra_data = {"webhook": data}
                tx.save(update_fields=['status', 'extra_data'])
    # log webhook
    PayoutLog.objects.create(
        provider="paystack", endpoint="webhook", request_payload=data)
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def paypal_webhook(request):
    body = request.body
    headers = request.headers
    try:
        data = json.loads(body)
    except Exception:
        data = None

    # verify using PayPal verify endpoint
    if not paypal_gateway.verify_webhook(headers, data):
        return HttpResponse(status=400)

    # examine event_type and resource
    event_type = data.get("event_type") if isinstance(data, dict) else None
    resource = data.get("resource", {}) if isinstance(data, dict) else {}

    # PayPal payout item id mapping: resource.batch_header.payout_batch_id or resource.payout_item_id
    provider_ref = None
    if resource:
        provider_ref = resource.get("payout_item_id") or resource.get(
            "payout_batch_id") or resource.get("sender_batch_id")

    # update WalletTransaction by transaction_id matching provider ref
    if provider_ref:
        tx_qs = WalletTransaction.objects.filter(transaction_id=provider_ref)
        if tx_qs.exists():
            tx = tx_qs.first()
            if event_type in ("PAYOUTS-ITEM.SUCCEEDED", "PAYOUTS-ITEM.SUCCESS", "PAYMENT.SALE.COMPLETED"):
                tx.status = "completed"
                tx.completed = True
                tx.extra_data = {"webhook": data}
                tx.save(update_fields=['status', 'completed', 'extra_data'])
            elif event_type in ("PAYOUTS-ITEM.FAILED", "PAYMENT.SALE.DENIED"):
                tx.status = "failed"
                tx.extra_data = {"webhook": data}
                tx.save(update_fields=['status', 'extra_data'])

    PayoutLog.objects.create(
        provider="paypal", endpoint="webhook", request_payload=data)
    return JsonResponse({"status": "ok"})
