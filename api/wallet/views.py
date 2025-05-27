from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from wallet.models import WalletTransaction
from api.wallet.serializers import WalletTransactionSerializer
from rest_framework.response import Response
import logging
import json

logger = logging.getLogger(__name__)


class WalletListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        queryset = WalletTransaction.objects.filter(user=self.request.user)
        logger.debug(
            f"WalletListView queryset for user={self.request.user.username}: {queryset.count()} transactions")
        for tx in queryset:
            logger.debug(
                f"Queryset transaction: id={tx.id}, user={tx.user.username}, type={tx.transaction_type}, job={tx.job.id if tx.job else 'None'}")
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        logger.debug(
            f"Serialized data for user={request.user.username}: {len(serializer.data)} transactions")
        for tx in serializer.data:
            logger.debug(
                f"Serialized transaction: id={tx['id']}, user={tx.get('user', 'N/A')}, type={tx['transaction_type']}, job={tx.get('job', 'N/A')}")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.debug(
                f"Paginated response for user={request.user.username}: {len(serializer.data)} transactions")
            response_data = serializer.data
        else:
            response_data = serializer.data
        logger.debug(
            f"Final response data: {json.dumps(response_data, indent=2)}")
        return Response(response_data)
