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
from core.models import Job
from api.payment.serializers import PaymentSerializer
from api.payment.paystack import Paystack  
from urllib.parse import urlencode,unquote


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
        callback_url = request.build_absolute_uri('/api/v1/payment/callback/')

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
            # Handle error gracefully
            request.session['payment_error'] = paystack_data
            return Response({'error': paystack_data}, status=status.HTTP_400_BAD_REQUEST)
        
            # request.session['payment_error'] = paystack_data
            # return redirect(job.get_payment_url())


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
        base_url = getattr(settings, "FRONTEND_BASE_URL", "https://nilltechsolutions.com")

        if not ref:
            error_params = urlencode(
                {'error': 'Missing reference in callback.'})
            return redirect(f"{base_url}/payment/failure/?{error_params}")

        payment = get_object_or_404(Payment, ref=ref)

        try:
            # Make a direct request to Paystack to retrieve full data
            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            verify_url = f"https://api.paystack.co/transaction/verify/{ref}"
            response = requests.get(verify_url, headers=headers)
            response.raise_for_status()
            paystack_data = response.json().get("data", {})
            

            # Save Paystack response to extra_data for auditing
            payment.extra_data = paystack_data
            payment.save(update_fields=["extra_data"])
            
            success_status = get_nested_values(paystack_data,'status')
            success_ref = get_nested_values(paystack_data, 'reference')
            
            if success_status == 'success' and payment.ref == success_ref:
                payment.verified = True
                payment.save()
                
                if payment.job:
                    job = payment.job
                    job.status = "open"
                    job.payment_verified = True 
                    job.save()
            

            # Now verify the payment using model method
            verified = payment.job.payment_verified

            if verified:
                return redirect(f"{base_url}/api/v1/jobs/{job.slug or job.id}/")
            else:
                error_params = urlencode(
                    {'error': 'Payment could not be verified. Please try again.'})
                return redirect(f"{base_url}/api/v1/jobs/{payment.job.slug or payment.job.id}/proceed-to-pay/?{error_params}")

        except requests.RequestException as e:
            error_params = urlencode(
                {'error': f"Paystack request failed: {str(e)}"})
            return redirect(f"{base_url}/api/v1/jobs/{payment.job.slug or payment.job.id}/proceed-to-pay/?{error_params}")

        except Exception as e:
            error_params = urlencode({'error': f"Internal error: {str(e)}"})
            return redirect(f"{base_url}/api/v1/jobs/{payment.job.slug or payment.job.id}/proceed-to-pay/?{error_params}")


class ProceedToPayAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, slug_or_id):
        error_message = request.GET.get('error')
        error_message = unquote(error_message) if error_message else None

        # Fetch job by slug or ID
        job = None
        try:
            if slug_or_id.isdigit():
                job = get_object_or_404(Job, id=int(slug_or_id))
            else:
                job = get_object_or_404(Job, slug=slug_or_id)
        except Exception as e:
            return Response({"error": f"Job not found: {str(e)}"}, status=404)

        # Get latest payment attempt for this job (optional)
        payment = Payment.objects.filter(
            job=job).order_by('-date_created').first()

        # Respond with relevant job + payment info + payment URL
        return Response({
            "message": "Proceed to payment",
            "job": {
                "id": job.id,
                "slug": job.slug,
                "title": job.title,
                "price": job.price,
                "status": job.status,
                "payment_verified": job.payment_verified,
            },
            "payment": {
                "ref": payment.ref if payment else None,
                "amount": payment.amount if payment else None,
                "verified": payment.verified if payment else None,
                "email": payment.email if payment else None,
            } if payment else None,
            "payment_url": request.build_absolute_uri(job.get_payment_url()),
            "error": error_message
        }, status=status.HTTP_200_OK)
