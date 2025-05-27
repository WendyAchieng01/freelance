from rest_framework import serializers
from wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field='username', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = ['id', 'user', 'transaction_type', 'payment_type',
                    'transaction_id', 'amount', 'status', 'job', 'timestamp', 'extra_data']
