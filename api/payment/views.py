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
from urllib.parse import urlencode


class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, **kwargs):
        """
        Automatically initiate payment using job ID or slug passed in URL.
        Price, email, and job are inferred from context – no manual input needed.
        """
        job_id = kwargs.get('id')
        job_slug = kwargs.get('slug')

        # Find the job using either ID or slug
        job = None
        if job_id:
            job = get_object_or_404(Job, id=job_id, client__user=request.user)
        elif job_slug:
            job = get_object_or_404(
                Job, slug=job_slug, client__user=request.user)
        else:
            return Response({'error': 'No job ID or slug provided.'}, status=status.HTTP_400_BAD_REQUEST)

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
            amount=payment.amount_value(),  # in kobo
            reference=payment.ref,
            callback_url=callback_url
        )

        if paystack_status:
            return Response({
                'authorization_url': paystack_data['authorization_url'],
                'reference': payment.ref,
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': paystack_data}, status=status.HTTP_400_BAD_REQUEST)


class PaymentCallbackView(APIView):
    permission_classes = [AllowAny] 

    def get(self, request):
        ref = request.GET.get('reference')
        base_url = getattr(settings, "FRONTEND_BASE_URL", "https://nilltechsolutions.com")

        if not ref:
            error_params = urlencode(
                {'error': 'Missing reference in callback.'})
            return redirect(f"{base_url}/payment/failure/?{error_params}")

        try:
            payment = get_object_or_404(Payment, ref=ref)
        except Exception as e:
            error_params = urlencode({'error': 'Payment record not found.'})
            return redirect(f"{base_url}/payment/failure/?{error_params}")

        try:
            verified = payment.verify_payment()
            if verified:
                # On success, redirect to Job detail page
                if payment.job.slug:
                    return redirect(f"{base_url}/api/v1/job/{payment.job.slug}/")
                else:
                    return redirect(f"{base_url}/api/v1/job/{payment.job.id}/")
            else:
                error_params = urlencode(
                    {'error': 'Payment could not be verified. Please try again.'})
                return redirect(f"{base_url}/api/v1/job/{payment.job.slug or payment.job.id}/proceed-to-pay/?{error_params}")
        except Exception as e:
            error_params = urlencode({'error': f"Internal error: {str(e)}"})
            return redirect(f"{base_url}/api/v1/job/{payment.job.slug or payment.job.id}/proceed-to-pay/?{error_params}")
