from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiExample
from accounts.models import Profile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review,JobBookmark,Notification
from accounts.models import FreelancerProfile
from api.accounts.serializers import ProfileMiniSerializer
import os
from datetime import datetime, time

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
        profile = obj.client.user.profile
        if obj.client:
            return {
                'id':obj.client.user.id,
                'first_name': obj.client.user.first_name,
                'last_name': obj.client.user.last_name,
                'username': obj.client.user.username,
                #'email': obj.client.user.email,
                'image': profile.profile_pic.url if profile.profile_pic else None
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
    has_applied_and_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = JobBookmark
        fields = ['id', 'slug', 'job', 'created_at','has_applied_and_bookmarked']
        
    def get_has_applied_and_bookmarked(self, obj):
        user = self.context.get('request').user
        if not user.is_authenticated:
            return False
        return obj.job.responses.filter(user=user).exists()




class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'filename', 'uploaded_at',
                  'file_size', 'content_type', 'thumbnail']


class MessageSerializer(serializers.ModelSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender', 'content',
                  'timestamp', 'is_read', 'is_deleted', 'attachments']
        read_only_fields = ['chat', 'sender',
                            'is_read', 'is_deleted', 'timestamp']

    def create(self, validated_data):
        # `chat` and `sender` are set in the view, `is_read` defaults to False
        return Message.objects.create(**validated_data)


class ChatSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    client = serializers.StringRelatedField()
    freelancer = serializers.StringRelatedField()

    class Meta:
        model = Chat
        fields = ['id', 'chat_uuid', 'job', 'client', 'freelancer',
                  'created_at', 'slug', 'active', 'messages']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'created_at', 'is_read', 'chat']
