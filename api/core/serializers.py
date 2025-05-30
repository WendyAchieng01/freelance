from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiExample
from accounts.models import Profile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
import os

User = get_user_model()


class NestedResponseSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Response
        fields = ['id', 'user', 'submitted_at', 'extra_data']

    def get_user(self, obj):
        return obj.user.username


class JobSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    selected_freelancer = serializers.SerializerMethodField()
    responses = NestedResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'category', 'description', 'price',
            'posted_date', 'deadline_date', 'status', 'client',
            'max_freelancers', 'preferred_freelancer_level','slug',
            'selected_freelancer', 'payment_verified', 'responses'
        ]
        read_only_fields = ['posted_date', 'client', 'payment_verified']

    def get_client(self, obj):
        return obj.client.user.username if obj.client else None

    def get_selected_freelancer(self, obj):
        return obj.selected_freelancer.username if obj.selected_freelancer else None


class ResponseSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    # Show job as nested details, read-only
    job = JobSerializer(read_only=True)
    # Accept job id on create/update
    job_id = serializers.PrimaryKeyRelatedField(
        queryset=Job.objects.all(), source='job', write_only=True
    )

    class Meta:
        model = Response
        fields = ['id', 'user', 'job', 'job_id', 'submitted_at', 'slug','extra_data']
        read_only_fields = ['user', 'submitted_at']

    def get_user(self, obj):
        return obj.user.username

    def validate(self, data):
        job = data.get('job')
        user = self.context['request'].user
        if job.responses.filter(user=user).exists():
            raise serializers.ValidationError(
                "You have already responded to this job.")
        if job.is_max_freelancers_reached or job.status != 'open':
            raise serializers.ValidationError("Cannot apply to this job.")
        return data

    def create(self, validated_data):
        return Response.objects.create(**validated_data)
    

class ChatSerializer(serializers.ModelSerializer):
    client = serializers.StringRelatedField(read_only=True)
    freelancer = serializers.StringRelatedField(read_only=True)
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all())

    class Meta:
        model = Chat
        fields = ['id', 'job', 'client', 'freelancer', 'created_at']
        read_only_fields = ['client', 'freelancer', 'created_at']
        examples = [
            OpenApiExample(
                'Chat Example',
                value={'job': 1},
                request_only=True
            )
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)
    chat = serializers.PrimaryKeyRelatedField(queryset=Chat.objects.all())
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender',
                  'content', 'timestamp', 'attachments']
        read_only_fields = ['sender', 'timestamp', 'attachments']
        examples = [
            OpenApiExample(
                'Message Example',
                value={'chat': 1, 'content': 'Hello, can we discuss the project?'},
                request_only=True
            )
        ]

    def get_attachments(self, obj):
        return [{'id': a.id, 'filename': a.filename, 'url': f'/api/v1/core/attachments/{a.id}/download/'}
                for a in obj.attachments.all()]


class MessageAttachmentSerializer(serializers.ModelSerializer):
    message = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all())
    file = serializers.FileField()

    class Meta:
        model = MessageAttachment
        fields = ['id', 'message', 'file', 'filename',
                  'uploaded_at', 'file_size', 'content_type']
        read_only_fields = ['filename', 'uploaded_at',
                            'file_size', 'content_type']
        examples = [
            OpenApiExample(
                'Attachment Example',
                value={'message': 1, 'file': 'example.pdf'},
                request_only=True
            )
        ]

    def validate_file(self, value):
        allowed_extensions = ['jpg', 'jpeg', 'png',
                              'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx']
        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"File extension '{ext}' is not allowed.")
        return value

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['filename'] = file.name
        validated_data['file_size'] = file.size
        validated_data['content_type'] = file.content_type
        return MessageAttachment.objects.create(**validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.StringRelatedField(read_only=True)
    recipient = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Review
        fields = ['id', 'reviewer', 'recipient', 'rating',
                  'comment', 'created_at', 'updated_at']
        read_only_fields = ['reviewer', 'created_at', 'updated_at']
        extra_kwargs = {
            'rating': {'choices': [(1, '1 - Poor'), (2, '2 - Below Average'), (3, '3 - Average'),
                                   (4, '4 - Good'), (5, '5 - Excellent')]}
        }
        examples = [
            OpenApiExample(
                'Review Example',
                value={'recipient': 2, 'rating': 5,
                       'comment': 'Excellent work!'},
                request_only=True
            )
        ]
