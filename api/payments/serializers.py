from rest_framework import serializers
from core.models import Job, Response as CoreResponse
from payments.models import PaypalPayments


from rest_framework import serializers
from payments.models import PaypalPayments


class InitiatePaymentSerializer(serializers.Serializer):
    response_id = serializers.IntegerField()


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaypalPayments
        fields = ['id', 'status', 'verified', 'amount', 'invoice']
