from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import InitiatePaymentSerializer, PaymentStatusSerializer
from core.models import Job, Response as CoreResponse
from payment.models import Payment
from accounts.models import Profile
from payments.models import PaypalPayments
from paypal.standard.forms import PayPalPaymentsForm
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED
from django.conf import settings
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.dispatch import receiver
from django.http import HttpResponse


class InitiatePayment(APIView):
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        job_id = serializer.validated_data['job_id']
        response_id = serializer.validated_data['response_id']

        job = get_object_or_404(Job, id=job_id)
        response = get_object_or_404(CoreResponse, id=response_id)

        # Check if the user is the job client
        if job.client.user != request.user:
            return Response(
                {"error": "You are not authorized to initiate this payment."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if the response belongs to the job
        if response.job != job:
            return Response(
                {"error": "The response does not belong to this job."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if a completed or failed payment already exists
        invoice = f"response-{job.id}-{response.id}"
        if PaypalPayments.objects.filter(invoice=invoice, status__in=['completed', 'failed']).exists():
            return Response(
                {"error": "Payment already processed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create payment
        payment = PaypalPayments.objects.create(
            job=job,
            invoice=invoice,
            amount=job.price,
            user=request.user,
            email=request.user.email,
            status='pending',
            extra_data={'response_id': str(response.id)}
        )

        # Prepare PayPal form
        paypal_receiver_email = getattr(
            settings, 'PAYPAL_RECEIVER_EMAIL', 'test-sandbox@example.com')
        paypal_dict = {
            "business": paypal_receiver_email,
            "amount": str(job.price),
            "item_name": job.title,
            "invoice": payment.invoice,
            "custom": str(response.id),
            "currency_code": "USD",
            "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
            "return_url": request.build_absolute_uri('/payments/success/'),
            "cancel_return": request.build_absolute_uri('/payments/cancel/'),
        }
        paypal_form = PayPalPaymentsForm(initial=paypal_dict)
        paypal_fields = paypal_form.render()
        print(f"PayPal form created for invoice={payment.invoice}")

        return Response({
            'payment_id': payment.id,
            'paypal_form': paypal_fields
        }, status=status.HTTP_201_CREATED)


class PaymentStatus(APIView):
    def get(self, request, payment_id):
        payment = get_object_or_404(PaypalPayments, id=payment_id)
        if payment.user != request.user:
            return Response(
                {"error": "You are not authorized to view this payment."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = PaymentStatusSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


@receiver(valid_ipn_received)
def payment_successful(sender, **kwargs):
    ipn_obj = sender
    print(
        f"IPN received: payment_status={ipn_obj.payment_status}, invoice={ipn_obj.invoice}")
    if ipn_obj.payment_status != ST_PP_COMPLETED:
        print(f"IPN not completed: status={ipn_obj.payment_status}")
        return

    try:
        job = Job.objects.get(id=int(ipn_obj.invoice.split('-')[1]))
        payment, created = Payment.objects.get_or_create(
            job=job,
            ref=ipn_obj.txn_id,
            defaults={
                'user': job.client.user,
                'amount': int(float(ipn_obj.mc_gross)),
                'email': ipn_obj.payer_email,
                'verified': True,
                'extra_data': {'paypal_invoice': ipn_obj.invoice}
            }
        )
        if not created:
            payment.verified = True
            payment.extra_data.update({'paypal_invoice': ipn_obj.invoice})
            payment.save()
    except Job.DoesNotExist:
        print(
            f"Error processing PayPal IPN: No job found for invoice={ipn_obj.invoice}")
    except Exception as e:
        print(f"Error processing PayPal IPN: {e}")


def payment_success(request):
    return HttpResponse("Payment successful")


def payment_cancel(request):
    return HttpResponse("Payment cancelled")
