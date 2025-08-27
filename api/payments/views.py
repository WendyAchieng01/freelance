
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

paypal_url = settings.PAYPAL_URL


class InitiatePaypalPayment(APIView):
    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        # Create or get pending payment
        payment, _ = PaypalPayments.objects.get_or_create(
            job=job,
            defaults={
                "user": request.user,
                "invoice": f"job-{job.id}",
                "amount": job.price,
                "status": "pending",
                "verified": False,
            }
        )

        try:
            access_token = get_paypal_access_token()
            url = "https://api-m.sandbox.paypal.com/v2/checkout/orders"
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
                    "return_url": f"{settings.FRONTEND_URL}/jobs/{job.slug}/success/",
                    "cancel_url": f"{settings.FRONTEND_URL}/jobs/{job.slug}/failed/"
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
            url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture"
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


@method_decorator(csrf_exempt, name='dispatch')
class PaypalWebhookView(APIView):
    authentication_classes = []  # PayPal doesn't send auth
    permission_classes = []      # open to PayPal only

    def post(self, request, *args, **kwargs):
        event = request.data
        logger.info(f"Received PayPal webhook: {event}")

        try:
            event_type = event.get("event_type")
            resource = event.get("resource", {})
            order_id = resource.get("id")

            payment = PaypalPayments.objects.filter(order_id=order_id).first()
            if not payment:
                return Response({"error": "Payment not found"}, status=404)

            if event_type == "CHECKOUT.ORDER.APPROVED":
                payment.status = "approved"
            elif event_type == "PAYMENT.CAPTURE.COMPLETED":
                payment.status = "completed"
                payment.verified = True
                # also mark job paid
                job = payment.job
                job.is_paid = True
                job.save()
            elif event_type == "PAYMENT.CAPTURE.DENIED":
                payment.status = "failed"

            payment.extra_data = event
            payment.save()

            return Response({"message": "Webhook processed"}, status=200)

        except Exception as e:
            logger.exception("Error processing PayPal webhook")
            return Response({"error": str(e)}, status=500)


class PaypalSuccessView(View):
    def get(self, request, invoice):
        try:
            payment = PaypalPayments.objects.get(invoice=invoice)
            job = payment.job

            message = "Payment successful! You can now proceed to hire!"            
            params = urlencode({
                "success": "true",
                "message": message,
            })
            
            redirect_url = f"{settings.FRONTEND_URL}/client/my-jobs/{job.slug}/?{params}"
            return redirect(redirect_url)
        
        except PaypalPayments.DoesNotExist:
            message = "Payment failed! Payment could not be found."            
            params = urlencode({
                "success": "false",
                "message": message,
            })

            redirect_url = f"{settings.FRONTEND_URL}/client/my-jobs/?{params}"
            return redirect(redirect_url)

class PaypalFailedView(View):
    def get(self, request, invoice):
        try:
            payment = PaypalPayments.objects.get(invoice=invoice)
            job = payment.job

            message = "Payment cancelled or failed."
            
            if payment.extra_data and "details" in payment.extra_data:
                details = payment.extra_data.get("details", [])
                if details and isinstance(details, list):
                    message = details[0].get("description", message)
            
            params = urlencode({
                "success": "false",
                "message": message,
            })
            
            return redirect(f"{settings.FRONTEND_URL}/client/my-jobs/{job.slug}/?{params}")
            
        except PaypalPayments.DoesNotExist:
            message = "Payment failed! Payment could not be found."
            params = urlencode({
                "success": "false",
                "message": message,
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

        # Human-readable message
        if payment.verified and payment.status.lower() == "completed":
            message = "Payment completed and verified."
        elif payment.status.lower() in ["pending", "processed"]:
            message = "Payment is pending verification."
        elif payment.status.lower() in ["failed", "cancelled"]:
            message = "Payment failed or was cancelled."
        else:
            message = f"Payment {payment.status}. Please try again or contact support."

        # Extract error details if available
        error_details = None
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
