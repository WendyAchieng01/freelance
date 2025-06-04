from rest_framework import generics,permissions
from rest_framework.permissions import IsAuthenticated
from wallet.models import WalletTransaction
from api.wallet.serializers import WalletTransactionSerializer
from rest_framework.response import Response
from rest_framework.views import APIView

import logging
import json

from core.models import Job

logger = logging.getLogger(__name__)


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WalletTransaction.objects.filter(user=self.request.user).order_by('-timestamp')


class WalletSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        total_earnings = WalletTransaction.total_earnings(request.user)
        completed_jobs = WalletTransaction.completed_jobs_total(request.user)
        return Response({
            "total_earnings": total_earnings,
            "completed_jobs": completed_jobs
        })


def assign_job_to_freelancer(job: Job):
    if job.selected_freelancer and job.status == 'open':
        job.status = 'in_progress'
        job.save()

        WalletTransaction.objects.create(
            user=job.selected_freelancer,
            transaction_type='job_picked',
            status='in_progress',
            job=job,
            amount=job.price
        )
