import logging
import time
from decimal import Decimal
from django.db import transaction
from django_q.tasks import async_task
from django.utils import timezone
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
    MAX_ATTEMPTS = 4
    def RETRY_BACKOFF(attempt): return min(2 ** attempt, 30)

    @staticmethod
    def _get_gateway(provider):
        gw = GATEWAYS.get(provider.lower())
        if gw is None:
            raise ValueError(
                f"No gateway configured for provider '{provider}'")
        # if mapping entry is a class, instantiate; if already instance, use it
        if isinstance(gw, type):
            return gw()
        # callable instance (factory) or object
        if callable(gw):
            try:
                return gw()
            except TypeError:
                # not callable, assume it's an instance
                return gw
        return gw

    @classmethod
    def execute_single(cls, tx: WalletTransaction, idempotency_key: str | None = None) -> dict:
        logger.info("⚡ EXECUTE_SINGLE start tx=%s", tx.id)

        # Ensure only eligible statuses are processed
        if tx.status not in ("pending", "failed"):
            msg = f"Transaction {tx.id} not payable (status={tx.status})"
            logger.warning(msg)
            return {"success": False, "error": msg}

        # Protect with DB lock to prevent double-pay from concurrent runs
        try:
            with transaction.atomic():
                tx_locked = WalletTransaction.objects.select_for_update().get(pk=tx.pk)

                # re-check inside lock
                if tx_locked.completed or tx_locked.status == "completed":
                    msg = f"Transaction {tx.id} already completed"
                    logger.info(msg)
                    return {"success": False, "error": msg}

                # determine provider: prefer tx.payment_type, then batch.provider
                provider = (tx_locked.payment_type or (
                    tx_locked.batch.provider if tx_locked.batch else None))
                if not provider:
                    msg = f"No provider configured for tx {tx.id}"
                    logger.error(msg)
                    return {"success": False, "error": msg}

                gateway = cls._get_gateway(provider)

                # build idempotency key
                if not idempotency_key:
                    bk = tx_locked.batch.reference if tx_locked.batch else tx_locked.id
                    idempotency_key = f"{provider}-payout-{bk}-tx-{tx_locked.id}"

                attempt = 0
                last_err = None
                success = False
                while attempt < cls.MAX_ATTEMPTS and not success:
                    attempt += 1
                    logger.info("Attempt %s for tx %s", attempt, tx_locked.id)
                    try:
                        res = gateway.payout(
                            tx_locked, idempotency_key=idempotency_key)
                    except Exception as exc:
                        logger.exception(
                            "Gateway exception for tx %s", tx_locked.id)
                        res = {"success": False, "provider_ref": None,
                               "raw": None, "error": str(exc)}

                    # always write PayoutLog in gateway; still log here
                    logger.debug("Gateway response for tx %s: %s",
                                 tx_locked.id, res)

                    if res.get("success"):
                        tx_locked.transaction_id = res.get("provider_ref")
                        tx_locked.extra_data = res.get("raw") or {}
                        tx_locked.status = "completed"
                        tx_locked.completed = True
                        tx_locked.save(
                            update_fields=["transaction_id", "extra_data", "status", "completed"])
                        success = True
                        logger.info(
                            "TX %s completed successfully", tx_locked.id)
                        return {"success": True, "provider_ref": tx_locked.transaction_id}
                    else:
                        last_err = res.get("error") or "unknown_error"
                        # set to in_progress while retrying, final attempt -> failed
                        tx_locked.status = "in_progress" if attempt < cls.MAX_ATTEMPTS else "failed"
                        tx_locked.extra_data = {
                            "attempts": attempt, "last_error": last_err, "raw": res.get("raw")}
                        tx_locked.save(update_fields=["status", "extra_data"])
                        logger.warning("TX %s attempt %s failed: %s",
                                       tx_locked.id, attempt, last_err)
                        if attempt < cls.MAX_ATTEMPTS:
                            sleep_s = cls.RETRY_BACKOFF(attempt)
                            time.sleep(sleep_s)

                # finished attempts
                return {"success": False, "error": last_err}
        except WalletTransaction.DoesNotExist:
            msg = f"Transaction {tx.pk} disappeared"
            logger.error(msg)
            return {"success": False, "error": msg}
        except Exception as exc:
            logger.exception("Unexpected error executing tx %s", tx.pk)
            return {"success": False, "error": str(exc)}

    @classmethod
    def execute_batch(cls, batch: PaymentBatch, async_run: bool = False):
        """
        Process all pending transactions in a batch. If async_run True, schedule via django-q async_task.
        """
        if async_run:
            async_task(
                "wallet.payouts.manager.PayoutManager.execute_batch", batch.id, False)
            return {"scheduled": True}

        logger.info("EXECUTE_BATCH start batch=%s", batch.reference)
        txs = batch.transactions.filter(
            status__in=["pending", "failed"]).select_related("user", "job")
        results = {"total": txs.count(), "success": 0, "failed": 0}
        for tx in txs:
            r = cls.execute_single(tx)
            if r.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1

        # finalize batch status
        if results["total"] == 0:
            batch.status = "failed"
            batch.note = "No eligible transactions"
        elif results["failed"] == 0 and results["success"] > 0:
            batch.status = "completed"
        elif results["success"] > 0 and results["failed"] > 0:
            batch.status = "partial"
        else:
            batch.status = "failed"
        batch.save(update_fields=["status", "note"])
        logger.info("EXECUTE_BATCH finished batch=%s status=%s",
                    batch.reference, batch.status)
        return results

    @classmethod
    def schedule_retry(cls, tx_id, delay_seconds=60):
        """Schedule a single tx retry via django-q after delay_seconds."""
        async_task("wallet.payouts.manager.PayoutManager.execute_single",
                   tx_id, schedule=delay_seconds)
        logger.info("Scheduled retry for tx %s in %s seconds",
                    tx_id, delay_seconds)
        return True
