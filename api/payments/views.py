from payments.models import PaypalPayments
from core.models import Job
from paypal.standard.models import ST_PP_COMPLETED
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from paypal.standard.forms import PayPalPaymentsForm
from paypal.standard.ipn.signals import valid_ipn_received
from payments.models import PaypalPayments
from core.models import Job, Response as coreResponse
from django.dispatch import receiver
from django.views import View
from django.utils.http import urlencode
from django.conf import settings

from .serializers import InitiatePaymentSerializer, PaymentStatusSerializer



paypal_url = settings.PAYPAL_URL



class InitiatePaypalPayment(APIView):
    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        # Ensure only one payment per job
        payment, created = PaypalPayments.objects.get_or_create(
            job=job,
            defaults={
                "user": request.user,
                "invoice": f"job-{job.id}",
                "price": job.price,
                "status": "pending"
            }
        )

        paypal_dict = {
            "business": settings.PAYPAL_RECEIVER_EMAIL,
            "amount": job.price,
            "item_name": job.title,
            "invoice": payment.invoice,
            "currency_code": "USD",
            "notify_url": request.build_absolute_uri(reverse("paypal-ipn")),
            "return_url": f"{settings.FRONTEND_URL}/api/v1/payments/payment/success/",
            "cancel_return": f"{settings.FRONTEND_URL}/api/v1/payments/payment/cancel/",
        }

        form = PayPalPaymentsForm(initial=paypal_dict)

        return Response({
            "paypal_url": str(paypal_url),
            "form_data": form.initial  
            # send to frontend to post
        })


class PaymentStatus(APIView):
    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaypalPayments, id=payment_id, user=request.user)
        serializer = PaymentStatusSerializer(payment)
        return Response(serializer.data)


class PaypalSuccessView(View):
    def get(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)

        # Optional: check if payment has already been verified
        if hasattr(job, "payment_verified") and job.payment_verified:
            message = "Payment successful!"
        else:
            message = "Payment processing. Please wait or click verify."

        domain = getattr(settings, "FRONTEND_URL", "https://nilltechsolutions.com")
        params = urlencode({"success": message})
        return redirect(f"{domain}/api/v1/job/{job.slug}/?{params}")


class PaypalFailedView(View):
    def get(self, request, job_id=None, slug=None):
        job = None
        if job_id:
            job = get_object_or_404(Job, id=job_id)
        elif slug:
            job = get_object_or_404(Job, slug=slug)

        domain = getattr(settings, "FRONTEND_URL", "https://nilltechsolutions.com")
        error = "Payment failed or was cancelled. Please try again."

        if job:
            return redirect(f"{domain}/api/v1/job/{job.slug}/proceed-to-pay/?error={error}")
        return redirect(f"{domain}/dashboard/?error={error}")


@receiver(valid_ipn_received)
def payment_successful(sender, **kwargs):
    ipn_obj = sender

    # Only proceed if payment is completed
    if ipn_obj.payment_status != ST_PP_COMPLETED:
        return

    if ipn_obj.receiver_email != settings.PAYPAL_RECEIVER_EMAIL:
        return  # ignore spoofed or misdirected IPN

    try:
        # Extract job ID from invoice, which should be in the format "job-<job_id>"
        invoice_parts = ipn_obj.invoice.split("-")
        if len(invoice_parts) != 2 or invoice_parts[0] != "job":
            return  # Invalid format

        job_id = int(invoice_parts[1])
        job = Job.objects.get(id=job_id)

        # Create or update the PaypalPayments record
        payment, created = PaypalPayments.objects.get_or_create(
            invoice=ipn_obj.invoice,
            defaults={
                "job": job,
                "user": job.client.user,
                "amount": float(ipn_obj.mc_gross),
                "email": ipn_obj.payer_email,
                "verified": True,
                "status": "completed",
                "extra_data": {"paypal_txn_id": ipn_obj.txn_id},
            },
        )

        if not created:
            payment.verified = True
            payment.status = "completed"
            payment.extra_data.update({"paypal_txn_id": ipn_obj.txn_id})
            payment.save()

        # Optional: mark the job as payment verified
        job.payment_verified = True
        job.save()

    except Exception as e:
        print(f"PayPal IPN error: {e}")
