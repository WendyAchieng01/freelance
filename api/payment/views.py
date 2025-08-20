import requests
from rest_framework.permissions import AllowAny,IsAuthenticatedOrReadOnly
from django.utils.http import urlencode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from payment.models import Payment
from payments.models import PaypalPayments
from core.models import Job
from api.payment.serializers import PaymentSerializer
from api.payment.paystack import Paystack  
from urllib.parse import urlencode,unquote
from django.conf import settings
from django.urls import reverse



class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        """
        Automatically initiate payment using job ID or slug passed in URL.
        Price, email, and job are inferred from context no manual input needed.
        """
        job_id = kwargs.get('id')
        job_slug = kwargs.get('slug')

        # Find the job using either ID or slug
        
        if job_id:
            job = get_object_or_404(Job, id=job_id, client__user=request.user)
        elif job_slug:
            job = get_object_or_404(
                Job, slug=job_slug, client__user=request.user)
        else:
            return Response({'error': 'No job ID or slug provided.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Prevent duplicate verified payments
        if job.payment_verified:
            #print(f"This is job payment url {job.get_payment_url()} while this is job absolute {job.get_absolute_url()}")

            return redirect(job.get_absolute_url())

        # Create a new payment instance also ref is  set automatically
        payment = Payment(
            user=request.user,
            amount=int(job.price),
            email=request.user.email,
            job=job,
        )
        payment.save()  #  ref is generated

        # Prepare callback URL
        callback_url = request.build_absolute_uri(
            reverse("payment-callback")
        )
        print('this is the callback url')
        print(callback_url)

        # Call Paystack to initialize the transaction
        paystack = Paystack()
        paystack_status, paystack_data = paystack.initialize_transaction(
            email=payment.email,
            amount=payment.amount_value(), 
            reference=payment.ref,
            callback_url=callback_url
        )

        if paystack_status:
            # Attempt automatic redirect
            if request.accepted_renderer.format == 'html' or 'text/html' in request.headers.get('Accept', ''):
                return redirect(paystack_data['authorization_url'])

            # Fallback for Swagger, Postman, JS frontend, etc.
            return Response({
                'authorization_url': paystack_data['authorization_url'],
                'reference': payment.ref,
                'message': 'Redirect failed? Click the Pay Now button.',
            }, status=status.HTTP_200_OK)

        else:
            error_msg = paystack_data.get(
                'message', 'Payment initialization failed.')
            print(error_msg)
            redirect_id = job.slug if hasattr(job, 'slug') and job.slug else job.id
            params = urlencode({'error': error_msg})
            
            return redirect(f"/jobs/{payment.job.slug or payment.job.id}/failed/?{params}")


def get_nested_values(data, *keys):
    """
    Retrieve values for one or more keys from a nested dictionary.
    Supports dot notation for nested keys (e.g., "authorization.bank").
    """
    results = {}

    for key in keys:
        parts = key.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break
        results[key] = value

    return results if len(keys) > 1 else results[keys[0]]


class PaymentCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ref = request.GET.get("reference")
        if not ref:
            error_params = urlencode(
                {'error': 'Missing reference in callback.'})
            return redirect(f"{settings.FRONTEND_URL}/jobs/unknown/failed/?{error_params}")

        payment = get_object_or_404(Payment, ref=ref)

        try:
            # Verify transaction with Paystack
            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            verify_url = f"https://api.paystack.co/transaction/verify/{ref}"
            response = requests.get(verify_url, headers=headers)
            response.raise_for_status()
            paystack_data = response.json().get("data", {})

            # Save full Paystack response
            payment.extra_data = paystack_data
            payment.save(update_fields=["extra_data"])

            success_status = paystack_data.get("status")
            gateway_response = paystack_data.get("gateway_response")

            if success_status == "success":
                payment.verified = True
                payment.save()
                if payment.job:
                    job = payment.job
                    job.status = "open"
                    job.payment_verified = True
                    job.save()

                    # Redirect to frontend success page
                    success_url = f"{settings.FRONTEND_URL}/jobs/{job.slug}/success/?ref={payment.ref}"
                    return redirect(success_url)

            else:
                reason = gateway_response or "Payment could not be verified."
                error_params = urlencode({"error": reason})

                error_url = f"{settings.FRONTEND_URL}/jobs/{payment.job.slug}/failed/?{error_params}"
                return redirect(error_url)

        except requests.RequestException as e:
            error_params = urlencode(
                {"error": f"Paystack request failed: {str(e)}"})
            return redirect(f"/jobs/{payment.job.slug}/failed/?{error_params}")

        except Exception as e:
            error_params = urlencode({"error": f"Internal error: {str(e)}"})
            return redirect(f"/jobs/{payment.job.slug}/failed/?{error_params}")


class ProceedToPayAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, slug_or_id, state=None):
        invoice = request.GET.get("invoice")

        # Locate the job
        try:
            if slug_or_id.isdigit():
                job = get_object_or_404(Job, id=int(slug_or_id))
            else:
                job = get_object_or_404(Job, slug=slug_or_id)
        except Exception as e:
            return Response(
                {"status": "failed", "error": f"Job not found: {str(e)}"},
                status=404,
            )

        # Select Payment model depending on provider
        if invoice:
            # PayPal flow
            payment = PaypalPayments.objects.filter(invoice=invoice).first()
            provider = "paypal"
        else:
            # Paystack flow
            payment = Payment.objects.filter(
                job=job).order_by("-date_created").first()
            provider = "paystack"

        # Handle failed payments
        if state == "failed" or (payment and not payment.verified):
            return Response(
                {
                    "status": "failed",
                    "provider": provider,
                    "job": {
                        "id": job.id,
                        "slug": job.slug,
                        "title": job.title,
                    },
                    "payment": {
                        "ref": getattr(payment, "invoice", None)
                        if provider == "paypal"
                        else getattr(payment, "ref", None),
                        "amount": str(getattr(payment, "amount", None)),
                        "verified": getattr(payment, "verified", None),
                    }
                    if payment
                    else None,
                    "error": getattr(payment, "error", "Payment failed"),
                },
                status=400,
            )

        # Success response
        payment_data = None
        if payment:
            if provider == "paystack":
                # Pick only useful nested data
                extra = {}
                if payment.extra_data:
                    extra = get_nested_values(
                        payment.extra_data,
                        "gateway_response",
                        "paid_at",
                        "channel",
                        "currency",
                        "fees",
                        "authorization.bank",
                        "authorization.channel",
                        "authorization.mobile_money_number",
                        "customer.email",
                    )

                payment_data = {
                    "ref": payment.ref,
                    "amount": payment.amount,
                    "verified": payment.verified,
                    "extra": extra,
                }

            elif provider == "paypal":
                payment_data = {
                    "ref": payment.invoice,
                    "amount": str(payment.amount),
                    "verified": payment.verified,
                    "status": payment.status,
                    "extra": payment.extra_data, 
                }

        return Response(
            {
                "status": "success",
                "provider": provider,
                "job": {
                    "id": job.id,
                    "slug": job.slug,
                    "title": job.title,
                    "price": job.price,
                    "status": job.status,
                    "payment_verified": job.payment_verified,
                },
                "payment": payment_data,
            },
            status=200,
        )
