import logging
import time
from decimal import Decimal
from django.db import transaction
from django_q.tasks import async_task
from django.utils import timezone
from wallet.services.payout_executor import execute_batch_payout
from wallet.models import WalletTransaction, PaymentBatch, PayoutLog
from api.wallet.gateways.paystack import PaystackGateway
from api.wallet.gateways.paypal import PayPalGateway

logger = logging.getLogger(__name__)

# Allow either class or instance in mapping
GATEWAYS = {
    "paystack": PaystackGateway,
    "paypal": PayPalGateway,
}


class PayoutManager:

    @classmethod
    def execute_batch(cls, batch: PaymentBatch, async_run=False):
        """
        Entry point for batch payouts.
        Delegates execution to payout_executor.
        """

        if async_run:
            from django_q.tasks import async_task
            async_task(
                "wallet.payouts.manager.PayoutManager.execute_batch",
                batch
            )
            return True

        try:
            execute_batch_payout(batch)
            return True

        except Exception as exc:
            logger.exception(
                "Batch payout failed batch=%s error=%s",
                batch.reference,
                exc,
            )
            return False


    @classmethod
    def execute_single(cls, tx: WalletTransaction):
        """
        Send a single WalletTransaction to the provider.
        """
        if not tx.payment_type:
            raise ValueError("Transaction has no payment_type")

        if tx.status != "pending":
            return {"success": False, "error": "Transaction not pending"}

        gateway = cls.get_gateway(tx.payment_type)

        result = gateway.single_payout(tx)

        if result.get("success"):
            tx.status = "in_progress"
            tx.provider_reference = result.get("provider_reference")
            tx.save(update_fields=["status", "provider_reference"])
            return {"success": True}
        else:
            tx.status = "failed"
            tx.save(update_fields=["status"])
            return {"success": False, "error": result.get("error", "Unknown error")}
