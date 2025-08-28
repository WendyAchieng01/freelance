from rest_framework import serializers
from wallet.models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    gross_amount = serializers.DecimalField(
        source='job.price', max_digits=10, decimal_places=2, read_only=True)
    net_earning = serializers.SerializerMethodField()
    payment_period = serializers.CharField(
        source='payment_period.name', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            'id','user','transaction_type','rate','payment_type',
            'transaction_id','amount','gross_amount','status','job',
            'job_title','payment_period','timestamp','completed','extra_data','net_earning',
        ]
        read_only_fields = ['user', 'timestamp', 'completed', 'extra_data']

    def get_net_earning(self, obj):
        return obj.net_earning()
