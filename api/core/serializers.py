from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiExample
from accounts.models import Profile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review,JobBookmark
from accounts.models import FreelancerProfile
from api.accounts.serializers import ProfileMiniSerializer
import os

User = get_user_model()


class NestedResponseSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Response
        fields = ['id', 'user', 'submitted_at', 'extra_data']

    def get_user(self, obj):
        try:
            profile = obj.user.profile 
            freelancer_profile = profile.freelancer_profile
            return {
                'id': obj.user.id,
                'first_name': obj.user.first_name,
                'last_name': obj.user.last_name,
                'username': obj.user.username,
                'portfolio': freelancer_profile.portfolio_link if freelancer_profile.portfolio_link else None,
                'image': profile.profile_pic.url if profile.profile_pic else None
            }
        except (Profile.DoesNotExist, FreelancerProfile.DoesNotExist):
            return obj.user.username if obj.user else None


class JobSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    selected_freelancer = serializers.SerializerMethodField()
    responses = NestedResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id','client', 'title', 'category', 'description', 'price',
            'posted_date', 'deadline_date', 'status',
            'max_freelancers', 'preferred_freelancer_level','slug',
            'selected_freelancer', 'payment_verified', 'responses'
        ]
        read_only_fields = ['posted_date', 'payment_verified']

    def get_client(self, obj):
        if obj.client:
            return {
                'id':obj.client.user.id,
                'first_name': obj.client.user.first_name,
                'last_name': obj.client.user.last_name,
                'username': obj.client.user.username,
                #'email': obj.client.user.email,
                'image':obj.client.profile_pic.url
            }
        return None

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
    reviewer = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username'
    )
    recipient = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field='username'
    )

    class Meta:
        model = Review
        fields = ['id', 'reviewer', 'recipient', 'rating',
                    'comment', 'created_at', 'updated_at']
        read_only_fields = ['reviewer', 'created_at', 'updated_at']


class JobSearchSerializer(serializers.ModelSerializer):
    client = serializers.StringRelatedField()
    selected_freelancer = serializers.StringRelatedField()

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'slug', 'category', 'description', 'price',
            'posted_date', 'deadline_date', 'status', 'client',
            'selected_freelancer', 'payment_verified'
        ]



class BookmarkedJobSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source='job.slug', read_only=True)
    job = JobSearchSerializer(read_only=True)

    class Meta:
        model = JobBookmark
        fields = ['id', 'slug', 'job', 'created_at']
