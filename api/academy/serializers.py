import os
from rest_framework import serializers
from academy.models import Training


class TrainingSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    job = serializers.SlugField(source='job.slug', read_only=True)
    client = serializers.PrimaryKeyRelatedField(read_only=True)
    pdf_document = serializers.FileField(
        required=False,
        allow_null=True,
        allow_empty_file=True,
        use_url=True
    )
    file_name = serializers.SerializerMethodField(read_only=True)
    file_size = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Training
        fields = [
            'url', 'title', 'texts', 'pdf_document', 'file_name', 'file_size',
            'video_url', 'job', 'client', 'slug'
        ]
        read_only_fields = ['url', 'job', 'client',
                            'slug', 'file_name', 'file_size']

    def validate_video_url(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError(
                "Video URL must start with http:// or https://"
            )
        return value

    def validate_pdf_document(self, value):
        if value == '':
            return None
        return value

    def get_url(self, obj):
        request = self.context.get('request')
        job_slug = self.context.get('job_slug') or (
            request and request.parser_context.get(
                'kwargs', {}).get('job_slug')
        )
        if request and job_slug and obj.slug:
            return request.build_absolute_uri(f'/api/v1/academy/trainings/{job_slug}/{obj.slug}/')
        return None

    def get_file_name(self, obj):
        if obj.pdf_document:
            filename = obj.pdf_document.name.split('/')[-1]
            return os.path.splitext(filename)[0]
        return None

    def get_file_size(self, obj):
        if obj.pdf_document and hasattr(obj.pdf_document, 'size'):
            size = obj.pdf_document.size
            for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024.0 or unit == 'TB':
                    return f"{size:.2f} {unit}"
                size /= 1024.0
        return None
