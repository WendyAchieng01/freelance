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
        if value is None or value == '':
            return None
        return value

    def get_file_name(self, obj):
        if obj.pdf_document:
            public_id = obj.pdf_document.public_id
            return os.path.splitext(public_id.split('/')[-1])[0]
        return None

    def get_file_size(self, obj):
        if obj.pdf_document and hasattr(obj.pdf_document, 'size'):
            size = obj.pdf_document.size
            for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024.0 or unit == 'TB':
                    return f"{size:.2f} {unit}"
                size /= 1024.0
        return None
