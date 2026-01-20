import json
import logging
import requests
from decimal import Decimal
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from django.conf import settings

from .base import BaseGateway
from accounts.models import Profile
from wallet.models import PayoutLog, WalletTransaction, PaymentBatch

logger = logging.getLogger(__name__)


class PaystackGateway(BaseGateway):
    provider_name = "paystack"
    base_url = getattr(settings, "PAYSTACK_BASE_URL",
                        "https://api.paystack.co")

    def __init__(self):
        self.sk = settings.PAYSTACK_SECRET_KEY

        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({
            "Authorization": f"Bearer {self.sk}",
            "Content-Type": "application/json",
        })

    # Utils

    def _safe_json(self, resp):
        try:
            return resp.json()
        except ValueError:
            try:
                return {"status": False, "raw_text": resp.text}
            except Exception:
                return {"status": False, "raw_text": "<unreadable>"}

    def _idempotency_key_for_tx(self, wallet_tx: WalletTransaction):
        batch_ref = wallet_tx.batch.reference if wallet_tx.batch else "no-batch"
        return f"paystack-payout-{batch_ref}-tx-{wallet_tx.id}"

    def _idempotency_key_for_batch(self, batch: PaymentBatch):
        return f"paystack-batch-{batch.reference}"

    # Phone + provider normalization

    def _normalize_phone_for_paystack(self, phone: str) -> str | None:
        """
        Always return in international format: 2547xxxxxxxx
        """
        if not phone:
            return None

        p = str(phone).strip().replace(" ", "").replace("-", "")

        if p.startswith("+"):
            p = p[1:]

        if p.startswith("0") and len(p) == 10 and p.isdigit():
            return "254" + p[1:]

        if p.startswith("7") and len(p) == 9 and p.isdigit():
            return "254" + p

        if p.startswith("254") and len(p) == 12 and p.isdigit():
            return p

        return None

    def _map_mobile_provider(self, provider_value: str) -> str:
        if not provider_value:
            return "MPESA"

        v = provider_value.strip().lower()

        if v in ("mpesa", "m-pesa", "m pesa"):
            return "MPESA"
        if "airtel" in v:
            return "AIRTEL"
        if "equit" in v:
            return "EQUITEL"

        return "MPESA"

    # Recipient handling

    def create_transfer_recipient_payload(self, payload: dict) -> dict:
        url = f"{self.base_url}/transferrecipient"

        try:
            resp = self.session.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            logger.exception("HTTP error creating transfer recipient")
            return {"success": False, "error": str(exc)}

        data = self._safe_json(resp)

        if resp.status_code in (200, 201) and data.get("status"):
            code = data.get("data", {}).get("recipient_code")
            if code:
                return {"success": True, "recipient_code": code}

        logger.error(
            "Recipient creation failed status=%s resp=%s",
            resp.status_code, json.dumps(data)[:2000]
        )
        return {"success": False, "error": data}

    def get_or_create_recipient_code(self, user) -> str | None:
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            logger.error("Profile missing for user id=%s",
                         getattr(user, "id", None))
            return None

        if getattr(profile, "paystack_recipient", None):
            return profile.paystack_recipient

        provider_code = self._map_mobile_provider(
            getattr(profile, "mobile_money_provider", None)
        )
        phone_number = self._normalize_phone_for_paystack(
            getattr(profile, "phone", None)
        )

        if not phone_number:
            logger.error(
                "Invalid phone for user id=%s phone=%s",
                user.id, getattr(profile, "phone", None)
            )
            return None

        payload = {
            "type": "mobile_money",
            "name": (
                f"{getattr(user, 'first_name', '')} "
                f"{getattr(user, 'last_name', '')}"
            ).strip() or getattr(user, "username", ""),
            "account_number": phone_number,
            "bank_code": provider_code,
            "currency": "KES",
        }

        result = self.create_transfer_recipient_payload(payload)

        if result.get("success"):
            code = result["recipient_code"]
            try:
                profile.paystack_recipient = code
                profile.save(update_fields=["paystack_recipient"])
            except Exception:
                logger.exception(
                    "Failed saving recipient_code for user id=%s", user.id
                )
            return code

        logger.error(
            "Failed creating recipient for user id=%s err=%s",
            user.id, json.dumps(result.get("error", {}))
        )
        return None

    # SINGLE PAYOUT

    def payout(self, wallet_tx: WalletTransaction, idempotency_key: str | None = None) -> dict:
        logger.info("PAYSTACK SINGLE PAYOUT tx=%s", wallet_tx.id)

        if not idempotency_key:
            idempotency_key = self._idempotency_key_for_tx(wallet_tx)

        try:
            amount_kobo = int(
                (Decimal(wallet_tx.amount) * 100).quantize(Decimal("1"))
            )
        except Exception as exc:
            err = f"Invalid amount for tx {wallet_tx.id}: {wallet_tx.amount} ({exc})"
            logger.exception(err)
            return {"success": False, "provider_ref": None, "raw": None, "error": err}

        recipient = self.get_or_create_recipient_code(wallet_tx.user)
        if not recipient:
            return {"success": False, "provider_ref": None, "raw": None, "error": "no_recipient"}

        payload = {
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient,
            "reason": f"Payout for job {getattr(wallet_tx.job, 'id', '')}",
        }

        url = f"{self.base_url}/transfer"
        headers = {"Idempotency-Key": idempotency_key}

        log = None
        try:
            log = PayoutLog.objects.create(
                wallet_transaction=wallet_tx,
                batch=wallet_tx.batch,
                provider=self.provider_name,
                endpoint="transfer",
                request_payload=payload,
                idempotency_key=idempotency_key,
            )
        except Exception:
            logger.exception(
                "Failed creating PayoutLog for tx %s", wallet_tx.id)

        try:
            resp = self.session.post(
                url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.exception(
                "Paystack single payout HTTP error tx=%s", wallet_tx.id)
            if log:
                log.error = str(exc)
                log.save(update_fields=["error"])
            return {"success": False, "provider_ref": None, "raw": None, "error": str(exc)}

        data = self._safe_json(resp)

        if log:
            try:
                log.response_payload = data
                log.status_code = resp.status_code
                log.save(update_fields=["response_payload", "status_code"])
            except Exception:
                logger.exception(
                    "Failed updating PayoutLog for tx %s", wallet_tx.id)

        if resp.status_code in (200, 201) and data.get("status"):
            provider_ref = (
                data.get("data", {}).get("reference")
                or data.get("data", {}).get("transfer_code")
            )
            return {"success": True, "provider_ref": provider_ref, "raw": data, "error": None}

        err = data.get("message") or data.get("error") or str(data)
        logger.warning(
            "Paystack single payout failed tx=%s err=%s", wallet_tx.id, err)
        return {"success": False, "provider_ref": None, "raw": data, "error": err}

    # BULK PAYOUT

    def bulk_payout_batch(self, batch: PaymentBatch) -> dict:
        """
        Sends ONE bulk transfer request for the entire batch.
        Paystack will fan-out internally and webhook each transfer.
        """
        logger.info("PAYSTACK BULK PAYOUT batch=%s", batch.reference)

        txs = batch.transactions.filter(status="pending")

        if not txs.exists():
            return {"success": False, "error": "no_pending_transactions"}

        transfers = []

        for tx in txs:
            recipient = self.get_or_create_recipient_code(tx.user)
            if not recipient:
                logger.error("Skipping tx %s: no recipient", tx.id)
                continue

            try:
                amount_kobo = int(
                    (Decimal(tx.amount) * 100).quantize(Decimal("1"))
                )
            except Exception:
                logger.exception(
                    "Invalid amount for tx %s amount=%s", tx.id, tx.amount)
                continue

            transfers.append({
                "amount": amount_kobo,
                "recipient": recipient,
                "reference": f"{batch.reference}:{tx.id}",
                "reason": f"Payout for job {getattr(tx.job, 'id', '')}",
            })

        if not transfers:
            return {"success": False, "error": "no_valid_transfers"}

        payload = {
            "source": "balance",
            "currency": "KES",
            "transfers": transfers,
        }

        url = f"{self.base_url}/transfer/bulk"
        idem_key = self._idempotency_key_for_batch(batch)
        headers = {"Idempotency-Key": idem_key}

        log = None
        try:
            print('working on creating logs for payment')
            log = PayoutLog.objects.create(
                batch=batch,
                provider=self.provider_name,
                endpoint="transfer/bulk",
                request_payload=payload,
                idempotency_key=idem_key,
            )
        except Exception:
            logger.exception(
                "Failed creating batch PayoutLog batch=%s", batch.reference)

        try:
            resp = self.session.post(
                url, json=payload, headers=headers, timeout=60)
        except requests.RequestException as exc:
            logger.exception(
                "Paystack bulk payout HTTP error batch=%s", batch.reference)
            if log:
                log.error = str(exc)
                log.save(update_fields=["error"])
            return {"success": False, "raw": None, "error": str(exc)}

        data = self._safe_json(resp)

        if log:
            try:
                log.response_payload = data
                log.status_code = resp.status_code
                log.save(update_fields=["response_payload", "status_code"])
            except Exception:
                logger.exception(
                    "Failed updating batch PayoutLog batch=%s", batch.reference)

        # === FIXED BLOCK ===
        if resp.status_code in (200, 201) and data.get("status"):
            # Paystack bulk response: data is a list, batch_code is in meta
            bulk_code = data.get("meta", {}).get("batch_code")

            # Optional: log individual transfers
            for t in data.get("data", []):
                logger.info(
                    "Queued transfer | ref=%s code=%s status=%s",
                    t.get("reference"),
                    t.get("transfer_code"),
                    t.get("status"),
                )

            return {
                "success": True,
                "bulk_code": bulk_code,
                "raw": data,
                "error": None,
            }

        err = data.get("message") or data.get("error") or str(data)
        logger.error("Paystack bulk payout failed batch=%s err=%s",
                    batch.reference, err)
        return {"success": False, "raw": data, "error": err}


    # Webhook verification

    def verify_webhook(self, headers, body) -> bool:
        import hmac
        import hashlib

        signature = headers.get(
            "X-Paystack-Signature") or headers.get("x-paystack-signature")
        secret = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", self.sk)

        if not signature:
            logger.warning("Missing Paystack webhook signature")
            return False

        computed = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

        try:
            return hmac.compare_digest(computed, signature)
        except Exception:
            logger.exception("Error comparing webhook signature")
            return False
