from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404, redirect
from payment.models import Payment
from api.payment.paystack import Paystack
from core.models import Job
from .serializers import PaymentInitiateSerializer


class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract validated data
        amount = serializer.validated_data['amount']
        email = serializer.validated_data['email']
        job_id = serializer.validated_data['job_id']
        extra_data = serializer.validated_data.get('extra_data', {})

        # Validate job ownership
        job = get_object_or_404(Job, id=job_id, client__user=request.user)

        # Create payment instance
        payment = Payment(
            user=request.user,
            amount=amount,
            email=email,
            job=job,
            extra_data=extra_data
        )
        payment.save()  # Generates a unique ref automatically

        # Initialize Paystack transaction
        paystack = Paystack()
        callback_url = request.build_absolute_uri('/api/payment/callback/')
        paystack_status, paystack_data = paystack.initialize_transaction(
            email=email,
            amount=amount,
            reference=payment.ref,
            callback_url=callback_url
        )

        if paystack_status:
            return Response({
                'authorization_url': paystack_data['authorization_url'],
                'reference': payment.ref
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': paystack_data}, status=status.HTTP_400_BAD_REQUEST)


class PaymentCallbackView(APIView):
    permission_classes = []  # Public endpoint for Paystack

    def get(self, request):
        ref = request.GET.get('reference')
        if not ref:
            return Response({'error': 'No reference provided'}, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(Payment, ref=ref)
        verified = payment.verify_payment()

        if verified:
            # Additional logic can be added here (e.g., handle response_id)
            frontend_success_url = 'https://frontend.com/payment/success'
            return redirect(frontend_success_url)
        else:
            frontend_failure_url = 'https://frontend.com/payment/failure'
            return redirect(frontend_failure_url)
