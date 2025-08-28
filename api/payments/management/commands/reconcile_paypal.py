import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from payments.models import PaypalPayments
from payments.paypal_api import get_paypal_access_token

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reconcile PayPal payments with PayPal API (safety net for missed webhooks)."

    def handle(self, *args, **options):
        access_token = get_paypal_access_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        payments = PaypalPayments.objects.exclude(
            status__in=["completed", "failed"])
        logger.info(f"Reconciling {payments.count()} PayPal payments...")

        for payment in payments:
            order_id = None
            if isinstance(payment.extra_data, dict):
                order_id = payment.extra_data.get("id")

            if not order_id:
                logger.warning(
                    f"Payment {payment.id} missing order_id, skipping")
                continue

            url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}"
            try:
                response = requests.get(url, headers=headers)
                data = response.json()

                if response.status_code != 200:
                    logger.error(
                        f"Failed to fetch PayPal order {order_id}: {data}")
                    continue

                status = data.get("status")

                if status == "COMPLETED":
                    self._mark_as_completed(payment, data)

                elif status == "APPROVED":
                    # Try auto-capture
                    capture_url = None
                    for link in data.get("links", []):
                        if link.get("rel") == "capture":
                            capture_url = link.get("href")
                            break

                    if capture_url:
                        capture_response = requests.post(
                            capture_url, headers=headers)
                        capture_data = capture_response.json()

                        if capture_response.status_code == 201:
                            self._mark_as_completed(payment, capture_data)
                            logger.info(
                                f"Payment {payment.id} auto-captured successfully.")
                        else:
                            logger.warning(
                                f"Payment {payment.id} could not be auto-captured: {capture_data}")

                elif status in ["DECLINED", "VOIDED"]:
                    payment.status = "failed"
                    payment.extra_data = data
                    payment.save()
                    logger.info(f"Payment {payment.id} marked as failed.")

            except Exception as e:
                logger.error(
                    f"Error reconciling payment {payment.id}: {e}", exc_info=True)

    def _mark_as_completed(self, payment, data):
        """Helper to mark payment & job as completed."""
        payment.status = "completed"
        payment.verified = True
        payment.extra_data = data
        payment.save()

        job = payment.job
        job.is_paid = True
        job.payment_verified = True
        job.status = "open"
        job.save()
