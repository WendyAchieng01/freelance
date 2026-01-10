import uuid
import logging
import requests
from .base import BaseGateway
from django.conf import settings
from wallet.models import PayoutLog
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


class PayPalGateway(BaseGateway):
    provider_name = "paypal"
    oauth_url = settings.PAYPAL_OAUTH_URL
    payouts_url = settings.PAYPAL_PAYOUTS_URL

    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.secret = settings.PAYPAL_SECRET
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.8,
                        status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _get_token(self):
        r = self.session.post(self.oauth_url, auth=(self.client_id, self.secret), data={
                                "grant_type": "client_credentials"}, timeout=30)
        r.raise_for_status()
        return r.json()["access_token"]

    def payout(self, wallet_tx, idempotency_key: str = None):
        """
        Uses wallet_tx.amount (KES net) -> converts to USD using settings.PAYOUT_EXCHANGE_RATES['KES_USD']
        """
        logger.warning("PAYPAL PAYOUT CALLED for TX %s", wallet_tx.id)
        
        if not idempotency_key:
            idempotency_key = f"paypal-payout-{wallet_tx.batch.reference if wallet_tx.batch else wallet_tx.id}-{uuid.uuid4().hex[:8]}"

        rates = getattr(settings, "PAYOUT_EXCHANGE_RATES", {})
        rate = rates.get("KES_USD")
        if rate is None:
            err = "no_exchange_rate"
            logger.error(
                "Missing KES->USD exchange rate in settings.PAYOUT_EXCHANGE_RATES")
            return {"success": False, "provider_ref": None, "raw": None, "error": err}

        try:
            amount_kes = float(wallet_tx.amount)
            usd_amount = amount_kes * float(rate)
            amount_str = f"{usd_amount:.2f}"
        except Exception as e:
            err = f"invalid_amount_conversion: {e}"
            logger.exception(err)
            return {"success": False, "provider_ref": None, "raw": None, "error": err}

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idempotency_key
        }

        item = {
            "recipient_type": "EMAIL",
            "amount": {"value": amount_str, "currency": "USD"},
            "receiver": getattr(wallet_tx.user, "email", None),
            "note": f"Payout for job {getattr(wallet_tx.job, 'id', '')}"
        }

        payload = {
            "sender_batch_header": {
                "sender_batch_id": str(wallet_tx.batch.reference if wallet_tx.batch else wallet_tx.id),
                "email_subject": "You have a payout"
            },
            "items": [item]
        }

        url = self.payouts_url
        log = PayoutLog.objects.create(
            wallet_transaction=wallet_tx,
            batch=wallet_tx.batch,
            provider=self.provider_name,
            endpoint=url,
            request_payload=payload,
            idempotency_key=idempotency_key
        )

        if not item["receiver"]:
            err = "no_paypal_email"
            log.response_payload = {"error": err}
            log.status_code = 400
            log.save(update_fields=['response_payload', 'status_code'])
            return {"success": False, "provider_ref": None, "raw": {"error": err}, "error": err}

        try:
            resp = self.session.post(
                url, json=payload, headers=headers, timeout=30)
            data = resp.json()
            log.response_payload = data
            log.status_code = resp.status_code
            log.save(update_fields=['response_payload', 'status_code'])

            if resp.status_code in (200, 201) and (data.get("batch_header") is not None or data.get("batch_header")):
                batch_header = data.get("batch_header", {})
                provider_ref = batch_header.get("payout_batch_id")
                return {"success": True, "provider_ref": provider_ref, "raw": data, "error": None}
            else:
                err = data.get("name") or data.get("message") or str(data)
                return {"success": False, "provider_ref": None, "raw": data, "error": err}
        except requests.RequestException as e:
            logger.exception("PayPal payout failed")
            log.error = str(e)
            log.save(update_fields=['error'])
            return {"success": False, "provider_ref": None, "raw": None, "error": str(e)}

    def verify_webhook(self, headers, body) -> bool:
        verification_url = settings.PAYPAL_VERIFY_WEBHOOK_URL
        token = self._get_token()
        verify_payload = {
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
            "cert_url": headers.get("PAYPAL-CERT-URL"),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": settings.PAYPAL_WEBHOOK_ID,
            "webhook_event": body
        }
        resp = requests.post(verification_url, json=verify_payload, headers={
                                "Authorization": f"Bearer {token}"}, timeout=30)
        try:
            ok = resp.status_code == 200 and resp.json().get(
                "verification_status") == "SUCCESS"
            return ok
        except Exception:
            return False
