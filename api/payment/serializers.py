from rest_framework import serializers
from payment.models import Payment
from core.models import Job




class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['amount', 'email', 'ref', 'verified',
                    'job', 'extra_data', 'date_created']
        read_only_fields = ['ref', 'verified', 'date_created']
