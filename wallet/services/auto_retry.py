import logging
from django.db import transaction
from api.wallet.gateways import get_payout_gateway
from wallet.models import WalletTransaction, PayoutLog

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def retry_failed_payouts():
    tx_ids = list(
        WalletTransaction.objects
        .filter(
            status="failed",
            completed=False,
            extra_data__retries__lt=MAX_RETRIES,
        )
        .values_list("id", flat=True)
    )

    for tx_id in tx_ids:
        with transaction.atomic():
            tx = WalletTransaction.objects.select_for_update().get(id=tx_id)
            retries = tx.extra_data.get("retries", 0)

        gateway = get_payout_gateway(tx.payment_type)
        result = gateway.payout(tx)

        with transaction.atomic():
            tx.extra_data["retries"] = retries + 1

            if result.get("success"):
                tx.status = "completed"
                tx.completed = True
                tx.provider_reference = result.get("provider_ref")
            else:
                tx.status = "failed"

            tx.save()

            PayoutLog.objects.create(
                wallet_transaction=tx,
                batch=tx.batch,
                provider=tx.payment_type,
                endpoint="retry_payout",
                response_payload=result,
                status_code=200 if result.get("success") else 400,
            )
