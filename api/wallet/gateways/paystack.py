import json
import uuid
import time
import logging
import requests
from .base import BaseGateway
from accounts.models import Profile
from django.conf import settings
from wallet.models import PayoutLog
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

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
            status_forcelist=[429, 500, 502, 503, 504]
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({
            "Authorization": f"Bearer {self.sk}",
            "Content-Type": "application/json"
        })

    def _idempotency_key(self, wallet_tx):
        # stable key for retries that ties to batch and tx id
        batch_ref = wallet_tx.batch.reference if wallet_tx.batch else "no-batch"
        return f"paystack-payout-{batch_ref}-tx-{wallet_tx.id}"

    # Helpers
    def _safe_json(self, resp):
        """Attempt to parse response JSON, return dict or raw text fallback."""
        try:
            return resp.json()
        except ValueError:
            text = None
            try:
                text = resp.text
            except Exception:
                text = "<unreadable response body>"
            return {"status": False, "error": "invalid_json_response", "raw_text": text}

    def _normalize_phone_for_paystack(self, phone: str) -> str | None:
        """
        Normalize phone number to the format expected by Paystack for mobile_money account_number:
        - Accepts formats: +2547xxxxxxx, 2547xxxxxxx, 07xxxxxxx
        - Returns a 10-digit numeric string starting with "07" or None if not parseable.
        """
        if not phone:
            return None

        p = str(phone).strip()
        # Remove spaces, dashes, and other non-numeric characters
        p = p.replace(" ", "").replace("-", "")

        # If it starts with "+" (international format), remove the "+" and country code
        if p.startswith("+"):
            p = p[1:]

        # If it starts with "0", ensure it's in the local format (07xxxxxxx)
        if p.startswith("0") and len(p) == 10:
            return p  # already in valid format

        # If it starts with "7" and has a valid length (9 or 10 digits), assume it's missing country code
        if p.startswith("7") and len(p) == 9:
            p = "07" + p[1:]  # prepend "07" to make it a valid local number

        # If it starts with "254" (Kenyan country code), remove the country code
        if p.startswith("254") and len(p) == 12:
            p = "0" + p[3:]  # remove country code and prepend "0"

        # Ensure the result is 10 digits and starts with "07"
        if p.startswith("07") and len(p) == 10 and p.isdigit():
            return p

        return None


    def _map_mobile_provider(self, provider_value: str) -> str:
        """
        Map various mobile provider labels used in Profile to Paystack expected bank_code.
        Default to 'mpesa' for Kenyan mobile money.
        """
        if not provider_value:
            return "mpesa"
        v = provider_value.strip().lower()
        # common mappings
        if v in ("mpesa", "m-pesa", "m pesa"):
            return "mpesa"
        if "airtel" in v:
            return "airtel" 
        # fallback
        return v

    # Transfer recipient creation
    def create_transfer_recipient_payload(self, payload: dict) -> dict:
        """
        Create a transfer recipient on Paystack.
        Payload should match Paystack's transferrecipient requirements for mobile_money.
        Returns dict: {"success": True, "recipient_code": "..."} or {"success": False, "error": <data>}
        """
        url = f"{self.base_url}/transferrecipient"
        try:
            print('This is the payload you want')
            print(payload)
            resp = self.session.post(url, json=payload, timeout=30)
        except requests.RequestException as exc:
            logger.exception("HTTP error when creating transfer recipient")
            return {"success": False, "error": str(exc)}

        data = self._safe_json(resp)

        if resp.status_code in (200, 201) and data.get("status"):
            recipient_code = data.get("data", {}).get("recipient_code")
            if recipient_code:
                return {"success": True, "recipient_code": recipient_code}
            else:
                logger.error(
                    "Paystack recipient creation response missing recipient_code: %s",
                    json.dumps(data)[:1000]
                )
                return {"success": False, "error": data}
        logger.error(
            "Paystack recipient creation failed status=%s response=%s",
            resp.status_code,
            json.dumps(data)[:2000]
        )
        return {"success": False, "error": data}

    def get_or_create_recipient_code(self, user) -> str | None:
        """
        Checks the user's Profile model for a recipient code. Creates one if missing.
        Returns recipient_code string or None.
        """
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            logger.error("Profile missing for user id=%s",
                         getattr(user, "id", None))
            return None

        # If already exists, return
        existing = getattr(profile, "paystack_recipient", None)
        if existing:
            return existing

        logger.info(
            "Recipient missing for user id=%s. Creating new one...", user.id)

        # normalize provider and phone
        provider_name = self._map_mobile_provider(
            getattr(profile, "mobile_money_provider", None))
        phone_number = self._normalize_phone_for_paystack(
            getattr(profile, "phone", None))

        if not phone_number:
            logger.error("Cannot create recipient: invalid or missing phone for user id=%s: phone=%s",
                         user.id, getattr(profile, "phone", None))
            return None

        # build payload according to Paystack mobile money requirements for KES
        payload = {
            "type": "mobile_money",
            "name": (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip() or getattr(user, "username", ""),
            "account_number": phone_number.replace("+", ""),
            "bank_code": provider_name.upper(),
            "currency": "KES",
        }
        print('This is the payload sent')
        print(payload)

        # create recipient
        result = self.create_transfer_recipient_payload(payload)

        if result.get("success"):
            recipient_code = result.get("recipient_code")
            try:
                # persist in both fields to satisfy existing checks elsewhere
                profile.paystack_recipient = recipient_code
                
                profile.save(update_fields=["paystack_recipient"])
            except Exception:
                logger.exception(
                    "Failed to save recipient_code to profile for user id=%s", user.id)
            logger.info("Created recipient %s for user id=%s",
                        recipient_code, user.id)
            return recipient_code
        else:
            logger.error("Failed to create recipient for user id=%s: %s",
                         user.id, json.dumps(result.get("error", {})))
            return None

    # Bulk payout
    def bulk_payout_batch(self, wallet_tx_list: list) -> dict:
        """
        Initiates a single bulk transfer API call for a list of WalletTransactions.
        """
        logger.info("PAYSTACK BULK PAYOUT called for %s transactions",
                    len(wallet_tx_list))

        transfers_payload = []
        for wallet_tx in wallet_tx_list:
            recipient_code = self.get_or_create_recipient_code(wallet_tx.user)

            if not recipient_code:
                logger.error(
                    "Skipping TX %s due to missing or uncreatable recipient code.", wallet_tx.id)
                continue

            try:
                amount_cents = int(round(float(wallet_tx.amount) * 100))
            except (ValueError, TypeError) as exc:
                logger.exception(
                    "Invalid amount format for tx %s: %s", wallet_tx.id, wallet_tx.amount)
                continue

            transfers_payload.append({
                "amount": amount_cents,
                "recipient": recipient_code,
                "reference": f"tx-{wallet_tx.id}-{str(uuid.uuid4())[:8]}",
                "reason": f"Payout for job {getattr(wallet_tx.job, 'id', '')}"
            })

        if not transfers_payload:
            return {"success": False, "error": "No valid transfers to process."}

        bulk_data = {
            "currency": "KES",
            "source": "balance",
            "transfers": transfers_payload
        }

        url = f"{self.base_url}/transfer/bulk"
        try:
            resp = self.session.post(url, json=bulk_data, timeout=60)
        except requests.RequestException as exc:
            logger.exception("Paystack bulk payout HTTP error")
            return {"success": False, "raw": None, "error": str(exc)}

        data = self._safe_json(resp)

        if resp.status_code in (200, 201) and data.get("status"):
            job_code = data.get("data", {}).get("job")
            return {"success": True, "raw": data, "error": None, "job_code": job_code}
        else:
            err = data.get("message") or data.get("error") or str(data)
            logger.error(
                "Paystack bulk payout failed status=%s error=%s", resp.status_code, err)
            return {"success": False, "raw": data, "error": err}

    # Single payout
    def payout(self, wallet_tx, idempotency_key: str | None = None) -> dict:
        """
        Expects wallet_tx.amount in KES. Paystack expects smallest unit (kobo) -> multiply by 100.
        """
        logger.info("PAYSTACK PAYOUT CALLED for TX %s", wallet_tx.id)
        if not idempotency_key:
            idempotency_key = self._idempotency_key(wallet_tx)

        try:
            amount_kobo = int(round(float(wallet_tx.amount) * 100))
        except Exception as e:
            err = f"Invalid amount for tx {wallet_tx.id}: {wallet_tx.amount} ({e})"
            logger.exception(err)
            return {"success": False, "provider_ref": None, "raw": None, "error": err}

        # ensure recipient exists or create one
        recipient = self.get_or_create_recipient_code(wallet_tx.user)

        payload = {
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient,
            "reason": f"Payout for job {getattr(wallet_tx.job, 'id', '')}"
        }

        url = f"{self.base_url}/transfer"
        headers = {"Idempotency-Key": idempotency_key}

        # create payout log record
        try:
            log = PayoutLog.objects.create(
                wallet_transaction=wallet_tx,
                batch=wallet_tx.batch,
                provider=self.provider_name,
                endpoint=url,
                request_payload=payload,
                idempotency_key=idempotency_key
            )
        except Exception:
            logger.exception(
                "Failed to create PayoutLog for tx %s", wallet_tx.id)
            # attempt to call provider

        if not recipient:
            err = "no_recipient"
            # attempt to update log if available
            try:
                log.response_payload = {"error": err}
                log.status_code = 400
                log.save(update_fields=['response_payload', 'status_code'])
            except Exception:
                # swallow save failures but keep logging
                logger.exception(
                    "Failed to update PayoutLog for missing recipient for tx %s", wallet_tx.id)

            return {"success": False, "provider_ref": None, "raw": {"error": err}, "error": err}

        # call Paystack transfer endpoint
        try:
            resp = self.session.post(
                url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.exception(
                "Paystack payout HTTP error for tx %s", wallet_tx.id)
            try:
                log.error = str(exc)
                log.save(update_fields=['error'])
            except Exception:
                pass
            return {"success": False, "provider_ref": None, "raw": None, "error": str(exc)}

        data = self._safe_json(resp)

        # persist response to log if available
        try:
            log.response_payload = data
            log.status_code = resp.status_code
            log.save(update_fields=['response_payload', 'status_code'])
        except Exception:
            logger.exception(
                "Failed to update PayoutLog with provider response for tx %s", wallet_tx.id)

        if resp.status_code in (200, 201) and data.get("status"):
            provider_ref = (data.get("data", {}).get("reference")
                            or data.get("data", {}).get("transfer_code"))
            return {"success": True, "provider_ref": provider_ref, "raw": data, "error": None}
        else:
            err = data.get("message") or data.get("error") or str(data)
            logger.warning(
                "Paystack payout failed for tx %s: %s", wallet_tx.id, err)
            return {"success": False, "provider_ref": None, "raw": data, "error": err}

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
        match = False
        try:
            match = hmac.compare_digest(computed, signature)
        except Exception:
            logger.exception("Error comparing webhook signature")
            return False
        return match
