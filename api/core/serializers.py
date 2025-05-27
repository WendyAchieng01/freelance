from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiExample
from accounts.models import Profile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
import os

User = get_user_model()


class JobSerializer(serializers.ModelSerializer):
    client = serializers.StringRelatedField(read_only=True)
    selected_freelancer = serializers.StringRelatedField(allow_null=True)

    class Meta:
        model = Job  # Fixed: Consolidated Meta class with model attribute
        fields = ['id', 'title', 'category', 'description', 'price', 'posted_date',
                  'deadline_date', 'status', 'client', 'max_freelancers',
                  'preferred_freelancer_level', 'selected_freelancer', 'payment_verified']
        read_only_fields = ['posted_date', 'client', 'payment_verified']
        extra_kwargs = {
            'category': {'choices': Job.CATEGORY_CHOICES},
            'status': {'choices': Job.STATUS_CHOICES},
            'preferred_freelancer_level': {'choices': [('entry', 'Entry Level'), ('intermediate', 'Intermediate'), ('expert', 'Expert')]}
        }
        examples = [
            OpenApiExample(
                'Job Example',
                value={
                    'title': 'Website Development',
                    'category': 'web_dev',
                    'description': 'Build a responsive website',
                    'price': 500.00,
                    'deadline_date': '2025-06-01',
                    'max_freelancers': 1,
                    'preferred_freelancer_level': 'intermediate'
                },
                request_only=True
            )
        ]


class ResponseSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all())
    sample_work_file = serializers.FileField(
        write_only=True, required=False, allow_null=True)

    class Meta:
        model = Response
        fields = ['id', 'user', 'job', 'submitted_at',
                  'extra_data', 'sample_work_file']
        read_only_fields = ['user', 'submitted_at']
        extra_kwargs = {
            'extra_data': {'required': False}
        }

    def validate(self, data):
        job = data.get('job')
        if job.responses.filter(user=self.context['request'].user).exists():
            raise serializers.ValidationError(
                {"job": "You have already responded to this job."})
        if job.is_max_freelancers_reached:
            raise serializers.ValidationError(
                {"job": "This job has reached its maximum freelancers."})
        return data

    def create(self, validated_data):
        sample_work_file = validated_data.pop('sample_work_file', None)
        validated_data.pop('user', None)  # Remove 'user' if present
        instance = Response.objects.create(
            user=self.context['request'].user, **validated_data)
        if sample_work_file:
            file_dir = os.path.join('Uploads', 'responses', str(instance.id))
            os.makedirs(file_dir, exist_ok=True)
            file_path = os.path.join(file_dir, sample_work_file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in sample_work_file.chunks():
                    destination.write(chunk)
            instance.extra_data = instance.extra_data or {}
            instance.extra_data['sample_work'] = {
                'filename': sample_work_file.name,
                'path': file_path,
                'content_type': sample_work_file.content_type,
                'size': sample_work_file.size
            }
            instance.save()
        return instance

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
