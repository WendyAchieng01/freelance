from rest_framework import serializers
from academy.models import Training
from core.models import Job


class TrainingSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='training-detail',
        lookup_field='slug'   
    )

    job = serializers.HyperlinkedRelatedField(
        view_name='job-detail-slug',
        lookup_field='slug',
        read_only=True
    )
    client = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='pk',
        read_only=True
    )
    pdf_document = serializers.FileField(
        required=False,
        allow_null=True,
        allow_empty_file=True,
        use_url=True,
    )

    class Meta:
        model = Training
        fields = ['url', 'title', 'texts', 'pdf_document',
                    'video_url', 'job', 'client', 'slug']
        read_only_fields = ['client', 'slug', 'job']
