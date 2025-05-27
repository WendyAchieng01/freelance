from rest_framework import serializers


class PaymentInitiateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=1, help_text="Amount in the base currency")
    email = serializers.EmailField(
        help_text="User's email for the transaction")
    job_id = serializers.IntegerField(help_text="ID of the job being paid for")
    extra_data = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Optional additional data (e.g., response_id)"
    )
