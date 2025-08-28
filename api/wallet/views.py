from rest_framework import generics,permissions,status
from rest_framework.permissions import IsAuthenticated
from wallet.models import WalletTransaction,Rate
from api.wallet.serializers import WalletTransactionSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from decimal import Decimal

import logging
import json

from core.models import Job

logger = logging.getLogger(__name__)


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show the logged-in user's transactions, newest first
        return (
            WalletTransaction.objects
            .filter(user=self.request.user)
            .select_related('job', 'payment_period')
            .order_by('-timestamp')
        )


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
            # amount will be auto-calculated in save()
        )
