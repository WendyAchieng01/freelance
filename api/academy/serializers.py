from rest_framework import serializers
from academy.models import Training
from core.models import Job


class TrainingSerializer(serializers.ModelSerializer):
    pdf_document = serializers.FileField(
        required=False,
        allow_null=True,
        allow_empty_file=True,
        use_url=True,
    )

    class Meta:
        model = Training
        fields = [
            'id', 'title', 'texts', 'pdf_document', 'video_url',
            'job', 'client', 'slug'
        ]
        read_only_fields = ['id', 'client', 'slug', 'job']

    def validate_job(self, value):
        user = self.context['request'].user
        if not Job.objects.filter(id=value.id, client=user.profile).exists():
            raise serializers.ValidationError(
                "You can only select jobs that belong to you.")
        return value
