from rest_framework import serializers
from core.models import Job, Response as CoreResponse
from payments.models import PaypalPayments


class InitiatePaymentSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    response_id = serializers.IntegerField()

    def validate(self, data):
        job_id = data.get('job_id')
        response_id = data.get('response_id')

        # Validate job existence
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise serializers.ValidationError(
                {"job_id": "Job does not exist."})

        # Validate response existence and association with job
        try:
            response = CoreResponse.objects.get(id=response_id, job=job)
        except CoreResponse.DoesNotExist:
            raise serializers.ValidationError(
                {"response_id": "Response does not belong to this job."})

        return data


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaypalPayments
        fields = ['id', 'status', 'verified', 'amount', 'invoice']
