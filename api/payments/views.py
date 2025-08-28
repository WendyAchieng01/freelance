
import requests
import logging
import json
import uuid
from django.views import View
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode
from django.dispatch import receiver
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import PaymentStatusSerializer
from paypal.standard.models import ST_PP_COMPLETED
from django.views.decorators.csrf import csrf_exempt
from paypal.standard.ipn.signals import valid_ipn_received
from django.utils.decorators import method_decorator
from django.shortcuts import redirect, get_object_or_404
from paypal.standard.forms import PayPalPaymentsForm
from .paypal_api import get_paypal_access_token

from core.models import Job
from payments.models import PaypalPayments

logger = logging.getLogger(__name__)



class InitiatePaypalPayment(APIView):
    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        # Create or get pending payment
        payment, _ = PaypalPayments.objects.get_or_create(
            job=job,
            defaults={
                "user": request.user,
                "invoice": f"job-{job.id}-{uuid.uuid4().hex[:10]}",
                "amount": job.price,
                "status": "pending",
                "verified": False,
            }
        )

        try:
            access_token = get_paypal_access_token()
            url = settings.PAYPAL_ORDERS_URL
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            body = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": str(payment.id),
                    "invoice_id": payment.invoice,
                    "amount": {
                        "currency_code": "USD",
                        "value": str(job.price)
                    }
                }],
                "application_context": {
                    "return_url": f"{settings.FRONTEND_URL}/jobs/{job.slug}/success/?invoice={payment.invoice}",
                    "cancel_url": f"{settings.FRONTEND_URL}/jobs/{job.slug}/failed/?invoice={payment.invoice}"
                }

            }

            response = requests.post(url, headers=headers, json=body)
            response.raise_for_status()
            order = response.json()

            # Save PayPal order ID
            payment.extra_data = order
            payment.save()

            # Find approval link
            approve_url = next(
                (link["href"]
                    for link in order["links"] if link["rel"] == "approve"),
                None
            )

            return Response({
                "order_id": order["id"],
                "approve_url": approve_url
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to create PayPal order: {e}", exc_info=True)
            return Response(
                {"error": "Could not initiate PayPal payment",
                    "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CapturePaypalPayment(APIView):
    def post(self, request, order_id):
        try:
            access_token = get_paypal_access_token()
            url = f"{settings.PAYPAL_ORDERS_URL}/{order_id}/capture"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            response = requests.post(url, headers=headers)
            data = response.json()

            if response.status_code == 201:
                invoice_id = data["purchase_units"][0].get("invoice_id")
                payment = PaypalPayments.objects.filter(
                    invoice=invoice_id).first()
                if payment:
                    payment.status = "completed"
                    payment.verified = True
                    payment.extra_data = data
                    payment.save()

                    job = payment.job
                    job.payment_verified = True
                    job.status = "open"
                    job.save()

                return Response(data, status=status.HTTP_200_OK)

            return Response(data, status=response.status_code)

        except Exception as e:
            logger.error(f"Failed to capture PayPal order: {e}", exc_info=True)
            return Response(
                {"error": "Could not capture PayPal payment",
                    "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaypalSuccessView(View):
    def get(self, request, invoice):
        try:
            # Locate payment by invoice
            payment = PaypalPayments.objects.filter(invoice=invoice).first()
            if not payment:
                message = "Payment record not found."
                params = urlencode({"success": "false", "message": message})
                return redirect(f"{settings.FRONTEND_URL}/client/my-jobs/?{params}")

            job = payment.job

            # If webhook has already verified it, mark success
            if payment.verified:
                message = "Payment successful! You can now proceed to hire!"
                params = urlencode({"success": "true", "message": message})
            else:
                # Webhook hasn’t updated yet or capture failed
                message = "Payment pending. Please refresh in a moment."
                params = urlencode({"success": "false", "message": message})

            redirect_url = f"{settings.FRONTEND_URL}/client/my-jobs/{job.slug}/?{params}"
            return redirect(redirect_url)

        except Exception as e:
            logger.error(f"Error in PayPal success view: {e}", exc_info=True)
            message = "Payment verification failed."
            params = urlencode({"success": "false", "message": message})
            return redirect(f"{settings.FRONTEND_URL}/client/my-jobs/?{params}")


class PaypalFailedView(View):
    def get(self, request, invoice):
        try:
            payment = PaypalPayments.objects.get(invoice=invoice)
            job = payment.job

            # Default failure message
            message = "Payment cancelled or failed."

            # If PayPal included details in extra_data, extract them
            if payment.extra_data and "details" in payment.extra_data:
                details = payment.extra_data.get("details", [])
                if details and isinstance(details, list):
                    message = details[0].get("description", message)

            params = urlencode({
                "success": "false",
                "message": message,
                "invoice": payment.invoice
            })

            return redirect(f"{settings.FRONTEND_URL}/client/my-jobs/{job.slug}/?{params}")

        except PaypalPayments.DoesNotExist:
            message = "Payment failed! Payment could not be found."
            params = urlencode({
                "success": "false",
                "message": message
                # No invoice since payment not found
            })
            redirect_url = f"{settings.FRONTEND_URL}/client/my-jobs/?{params}"
            return redirect(redirect_url)



class PaymentStatus(APIView):
    """
    Returns the current status of a PayPal payment.
    Includes verification status, human-readable message, and error details.
    """

    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaypalPayments, id=payment_id, user=request.user)
        serializer = PaymentStatusSerializer(payment)

        message = None
        error_details = None

        # Completed & verified
        if payment.verified and payment.status.lower() == "completed":
            message = "Payment completed and verified."

        # Pending states
        elif payment.status.lower() in ["pending", "processed"]:
            message = "Payment is pending verification."
            # Try to extract pending reason from PayPal response
            if isinstance(payment.extra_data, dict):
                resource = payment.extra_data.get("resource", {})
                if isinstance(resource, dict):
                    status_details = resource.get("status_details")
                    if status_details and "reason" in status_details:
                        pending_reason = status_details["reason"]
                        message += f" (Reason: {pending_reason.replace('_', ' ').title()})"

        # Failed / cancelled
        elif payment.status.lower() in ["failed", "cancelled"]:
            message = "Payment failed or was cancelled."

        else:
            message = f"Payment {payment.status}. Please try again or contact support."

        # Extract error details if available
        if isinstance(payment.extra_data, dict):
            if "details" in payment.extra_data:
                details = payment.extra_data.get("details", [])
                if details and isinstance(details, list):
                    error_details = details[0].get("description")

        data = serializer.data
        data["message"] = message
        if error_details:
            data["error_details"] = error_details

        return Response(data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class PaypalWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        event = request.data
        logger.info(f"Received PayPal webhook: {event}")

        try:
            event_type = event.get("event_type")
            resource = event.get("resource", {})

            # Extract invoice_id and order_id safely across event types
            invoice_id = None
            order_id = resource.get("id")

            # CHECKOUT.ORDER.APPROVED → invoice is inside purchase_units
            if resource.get("purchase_units"):
                invoice_id = resource["purchase_units"][0].get("invoice_id")

            # For PAYMENT.CAPTURE.* → invoice is usually at root level
            if not invoice_id and "invoice_id" in resource:
                invoice_id = resource["invoice_id"]

            # If still missing → check supplementary_data.related_ids
            if not invoice_id:
                related_ids = resource.get(
                    "supplementary_data", {}).get("related_ids", {})
                if "order_id" in related_ids:
                    order_id = related_ids["order_id"]

            logger.info(
                f"Resolved invoice_id={invoice_id}, order_id={order_id}")

            # Try to match payment
            payment = None
            if invoice_id:
                payment = PaypalPayments.objects.filter(
                    invoice=invoice_id).first()
            if not payment and order_id:
                payment = PaypalPayments.objects.filter(
                    extra_data__id=order_id).first()

            if not payment:
                logger.warning(
                    f"No payment found for invoice={invoice_id}, order={order_id}")
                return Response({"error": "Payment not found"}, status=404)

            # keep last event for debugging
            payment.extra_data = {**payment.extra_data, "last_event": event}
            payment.save(update_fields=["extra_data"])

            if event_type == "CHECKOUT.ORDER.APPROVED":
                if not payment.verified:
                    capture_url = None
                    for link in resource.get("links", []):
                        if link.get("rel") == "capture":
                            capture_url = link.get("href")
                            break

                    if capture_url:
                        access_token = get_paypal_access_token()
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {access_token}",
                        }
                        capture_response = requests.post(
                            capture_url, headers=headers)
                        capture_data = capture_response.json()

                        if capture_response.status_code == 201:
                            payment.status = "completed"
                            payment.verified = True
                            payment.extra_data = {
                                **payment.extra_data,
                                "capture": capture_data,
                            }
                            payment.save()

                            job = payment.job
                            job.is_paid = True
                            job.payment_verified = True
                            job.status = "open"
                            job.save()

                            logger.info(
                                f"Payment captured successfully via webhook: {payment.invoice}")
                        else:
                            logger.error(
                                f"Capture failed via webhook: {capture_data}")

            elif event_type == "PAYMENT.CAPTURE.COMPLETED":
                if not payment.verified:
                    payment.status = "completed"
                    payment.verified = True
                    payment.extra_data = {
                        **payment.extra_data,
                        "capture_completed": resource,
                    }
                    payment.save()

                    job = payment.job
                    job.is_paid = True
                    job.payment_verified = True
                    job.status = "open"
                    job.save()

            elif event_type == "PAYMENT.CAPTURE.DENIED":
                payment.status = "failed"
                payment.extra_data = {**payment.extra_data, "denied": resource}
                payment.save()

            elif event_type == "PAYMENT.CAPTURE.PENDING":
                payment.status = "pending"
                payment.extra_data = {
                    **payment.extra_data, "pending": resource}
                payment.save()
                logger.info(
                    f"Payment marked as pending for invoice={invoice_id}")

            return Response({"message": "Webhook processed"}, status=200)

        except Exception as e:
            logger.exception("Error processing PayPal webhook")
            return Response({"error": str(e)}, status=500)
