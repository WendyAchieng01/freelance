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


class ApplyResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ['extra_data']


class ResponseListSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Response
        fields = ['id', 'user', 'extra_data', 'submitted_at']

    def get_user(self, obj):
        profile = getattr(obj.user, 'profile', None)
        return {
            'username': obj.user.username,
            'email': obj.user.email,
            'bio': profile.bio if profile else '',
            'location': profile.location if profile else '',
            'profile_pic': profile.profile_pic.url if profile and profile.profile_pic else None,
        }
        

class FreelancerBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class JobResponseBriefSerializer(serializers.ModelSerializer):
    user = FreelancerBriefSerializer()

    class Meta:
        model = Response
        fields = ['id', 'user', 'submitted_at']


class JobWithResponsesSerializer(serializers.ModelSerializer):
    responses = JobResponseBriefSerializer(many=True)

    class Meta:
        model = Job
        fields = ['id', 'title', 'description', 'responses']


class ChatSerializer(serializers.ModelSerializer):
    client = serializers.StringRelatedField(read_only=True)
    freelancer = serializers.StringRelatedField(read_only=True)
    job = serializers.PrimaryKeyRelatedField(
        queryset=Job.objects.filter(payment_verified=True))
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = Chat
        fields = ['id', 'job', 'client', 'freelancer', 'created_at', 'slug']
        read_only_fields = ['client', 'freelancer', 'created_at', 'slug']

    def create(self, validated_data):
        user = self.context['request'].user
        profile = user.profile
        job = validated_data['job']

        if not job.payment_verified:
            raise serializers.ValidationError(
                "Payment must be verified to start chat.")

        if profile.user_type == 'client':
            chat = Chat.objects.create(
                client=profile, freelancer=job.selected_freelancer.profile, **validated_data)
        elif profile.user_type == 'freelancer':
            chat = Chat.objects.create(
                freelancer=profile, client=job.client, **validated_data)
        else:
            raise serializers.ValidationError("Invalid user role.")
        return chat


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)
    chat = serializers.PrimaryKeyRelatedField(read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender',
                    'content', 'timestamp', 'attachments']
        read_only_fields = ['id', 'chat',
                            'sender', 'timestamp', 'attachments']

    def get_attachments(self, obj):
        return [{'id': a.id, 'filename': a.filename, 'url': f'/api/v1/core/attachments/{a.id}/download/'} for a in obj.attachments.all()]



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

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower().lstrip('.')
        if ext not in ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx']:
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
