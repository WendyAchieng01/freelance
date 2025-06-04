from rest_framework import serializers
from wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    net_earning = serializers.SerializerMethodField()
    gross_amount = serializers.DecimalField(source='job.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'user', 'transaction_type', 'rate', 'payment_type',
            'transaction_id', 'amount', 'gross_amount',  'status', 'job', 'job_title',
            'timestamp', 'completed', 'extra_data', 'net_earning'
        ]

    def get_net_earning(self, obj):
        return obj.net_earning()
