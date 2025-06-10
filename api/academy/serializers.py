from rest_framework import serializers
from academy.models import Training


class TrainingSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(
        read_only=True)  # Optional: Generate URL manually
    slug = serializers.SlugField(read_only=True)
    job = serializers.SlugField(
        source='job.slug', read_only=True)  # Use job slug
    client = serializers.PrimaryKeyRelatedField(
        read_only=True)  # Use client PK
    pdf_document = serializers.FileField(
        required=False,
        allow_null=True,
        allow_empty_file=True,
        use_url=True
    )

    class Meta:
        model = Training
        fields = ['url', 'title', 'texts', 'pdf_document',
                  'video_url', 'job', 'client', 'slug']
        read_only_fields = ['url', 'job', 'client', 'slug']

    def validate_video_url(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError(
                "Video URL must start with http:// or https://")
        return value

    def validate_pdf_document(self, value):
        if value == '':
            return None
        return value

    def get_url(self, obj):
        # Manually construct URL
        request = self.context.get('request')
        job_slug = self.context.get('job_slug') or (
            request and request.parser_context.get('kwargs', {}).get('job_slug'))
        if request and job_slug and obj.slug:
            return request.build_absolute_uri(f'/api/v1/academy/trainings/{job_slug}/{obj.slug}/')
        return None  
