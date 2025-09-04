from decimal import Decimal
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import generics,permissions,status
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.models import WalletTransaction,Rate
from api.wallet.serializers import WalletTransactionSerializer,ClientTransactionSerializer
from payments.models import PaypalPayments
from payment.models import Payment
from datetime import datetime,timezone
from django.utils import timezone as dj_timezone


import logging
import json

from core.models import Job

logger = logging.getLogger(__name__)


def normalize_dt(dt):
    if dt is None:
        # Make sure datetime.min is tz-aware
        return datetime.min.replace(tzinfo=timezone.utc)
    if dj_timezone.is_naive(dt):
        return dj_timezone.make_aware(dt, dj_timezone.get_current_timezone())
    return dt


class WalletTransactionListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.user_type == "client":
            return ClientTransactionSerializer
        return WalletTransactionSerializer

    def list(self, request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)

        if profile and profile.user_type == "freelancer":
            # standard DRF list() with pagination
            return super().list(request, *args, **kwargs)

        elif profile and profile.user_type == "client":
            transactions = self.get_client_transactions()
            total_spent = self.get_client_total_spent()

            page = self.paginate_queryset(transactions)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # add total_spent into paginated response
                response = self.get_paginated_response(serializer.data)
                response.data["total_spent"] = float(total_spent)
                return response

            serializer = self.get_serializer(transactions, many=True)
            return Response({
                "results": serializer.data,
                "total_spent": float(total_spent)
            })

        return Response([])

    def get_queryset(self):
        """
        Freelancer flow only.
        """
        user = self.request.user
        profile = getattr(user, "profile", None)

        if profile and profile.user_type == "freelancer":
            return (
                WalletTransaction.objects
                .filter(user=user)
                .select_related("job", "payment_period")
                .order_by("-timestamp")
            )
        return WalletTransaction.objects.none()

    def get_client_transactions(self):
        """
        Merge Paystack + PayPal into transaction list for client
        """
        user = self.request.user
        paystack_qs = Payment.objects.filter(user=user).select_related("job")
        paypal_qs = PaypalPayments.objects.filter(user=user).select_related("job")

        transactions = []

        for p in paystack_qs:
            transactions.append({
                "id": f"paystack-{p.id}",
                "job_id": p.job.id,
                "job_title": p.job.title,
                "amount": Decimal(p.amount),
                "verified": p.verified,
                "status": (
                    "completed" if p.job.status == "completed" else
                    "pending" if p.job.status == "in_progress" else
                    "initiated"
                ),
                "source": "paystack",
                "created_at": p.date_created, 
            })

        for p in paypal_qs:
            transactions.append({
                "id": f"paypal-{p.id}",
                "job_id": p.job.id,
                "job_title": p.job.title,
                "amount": p.amount,
                "verified": p.verified and p.status == "completed",
                "status": (
                    "completed" if p.job.status == "completed" else
                    "pending" if p.job.status == "in_progress" else
                    "initiated"
                ),
                "source": "paypal",
                "created_at": getattr(p, "created_at", None), 
            })

        transactions.sort(
            key=lambda x: normalize_dt(x["created_at"]),
            reverse=True,
        )
        return transactions

    def get_client_total_spent(self):
        """
        Aggregate verified payments for the client
        """
        user = self.request.user

        total_paystack = Payment.objects.filter(user=user, verified=True).aggregate(
            total=Coalesce(Sum("amount", output_field=DecimalField()),
                            0, output_field=DecimalField())
        )["total"]

        total_paypal = PaypalPayments.objects.filter(
            user=user, verified=True, status="completed"
        ).aggregate(
            total=Coalesce(Sum("amount", output_field=DecimalField()),
                            0, output_field=DecimalField())
        )["total"]

        return total_paystack + total_paypal


class WalletSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        gross_earnings = WalletTransaction.total_gross_earnings(request.user)
        net_earnings = WalletTransaction.total_earnings(request.user)
        completed_jobs = WalletTransaction.completed_jobs_total(request.user)

        return Response({
            "gross_earnings": gross_earnings,
            "net_earnings": net_earnings,
            "completed_jobs": completed_jobs,
        }, status=status.HTTP_200_OK)


def assign_job_to_freelancer(job: Job):
    if job.selected_freelancer and job.status == 'open':
        job.status = 'in_progress'
        job.save()

        # get latest platform fee
        try:
            rate = Rate.objects.latest('effective_from').rate_amount
        except Rate.DoesNotExist:
            rate = Decimal('5.00')

        WalletTransaction.objects.create(
            user=job.selected_freelancer,
            transaction_type='job_picked',
            status='in_progress',
            job=job,
            rate=rate
        )
