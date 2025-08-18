from .serializers import PaymentStatusSerializer
from paypal.standard.models import ST_PP_COMPLETED
from django.dispatch import receiver
from paypal.standard.ipn.signals import valid_ipn_received
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from urllib.parse import urlencode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from paypal.standard.forms import PayPalPaymentsForm
from django.conf import settings
from django.urls import reverse
from core.models import Job
from payments.models import PaypalPayments


paypal_url = settings.PAYPAL_URL


class InitiatePaypalPayment(APIView):
    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        payment, created = PaypalPayments.objects.get_or_create(
            job=job,
            defaults={
                "user": request.user,
                "invoice": f"job-{job.id}",
                "amount": job.price,
                "status": "pending",
                "verified": False,
            }
        )

        success_params = urlencode({"invoice": payment.invoice})
        fail_params = urlencode({"invoice": payment.invoice})

        paypal_dict = {
            "business": settings.PAYPAL_RECEIVER_EMAIL,
            "amount": job.price,
            "item_name": job.title,
            "invoice": payment.invoice,
            "currency_code": "USD",
            "notify_url": request.build_absolute_uri(reverse("paypal-ipn")),
            "return_url": f"{settings.FRONTEND_URL}/jobs/{job.slug}/success/?{success_params}",
            "cancel_return": f"{settings.FRONTEND_URL}/jobs/{job.slug}/failed/?{fail_params}",
        }

        form = PayPalPaymentsForm(initial=paypal_dict)

        return Response({
            "paypal_url": settings.PAYPAL_URL,
            "form_data": form.initial
        }, status=status.HTTP_200_OK)


class PaypalSuccessView(View):
    def get(self, request, invoice):
        payment = get_object_or_404(PaypalPayments, invoice=invoice)
        job = payment.job
        return redirect(f"{settings.FRONTEND_URL}/jobs/{job.slug}/success/?ref={payment.invoice}")


class PaymentStatus(APIView):
    """
    Returns the current status of a PayPal payment.
    Includes verification status and human-readable message.
    """

    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaypalPayments, id=payment_id, user=request.user)
        serializer = PaymentStatusSerializer(payment)

        # Human-readable message
        if payment.verified and payment.status == "completed":
            message = "Payment completed and verified."
        elif payment.status.lower() in ["pending", "processed"]:
            message = "Payment is pending verification."
        else:
            message = f"Payment {payment.status}. Please try again or contact support."

        data = serializer.data
        data["message"] = message

        return Response(data, status=status.HTTP_200_OK)


class PaypalFailedView(View):
    def get(self, request, invoice):
        try:
            payment = PaypalPayments.objects.get(invoice=invoice)
            job = payment.job
        except PaypalPayments.DoesNotExist:
            return redirect(f"{settings.FRONTEND_URL}/jobs/?error=payment_not_found")

        error_msg = "Payment failed or was cancelled."
        params = urlencode({"error": error_msg})
        return redirect(f"{settings.FRONTEND_URL}/jobs/{job.slug}/failed/?{params}")


class PaymentStatus(APIView):
    """
    Returns the current status of a PayPal payment.
    Includes verification status and human-readable message.
    """

    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaypalPayments, id=payment_id, user=request.user)
        serializer = PaymentStatusSerializer(payment)

        # Human-readable message
        if payment.verified and payment.status == "completed":
            message = "Payment completed and verified."
        elif payment.status.lower() in ["pending", "processed"]:
            message = "Payment is pending verification."
        else:
            message = f"Payment {payment.status}. Please try again or contact support."

        data = serializer.data
        data["message"] = message

        return Response(data, status=status.HTTP_200_OK)
