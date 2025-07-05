from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiExample
from accounts.models import Profile,Skill
from core.models import Job,JobCategory, Response, Chat, Message, MessageAttachment, Review,JobBookmark,Notification
from accounts.models import FreelancerProfile
from api.accounts.serializers import ProfileMiniSerializer,SkillSerializer
import os
from datetime import datetime, time
from django.utils import timezone
from api.core.utils import validate_file


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
                'profile_pic': profile.profile_pic.url if profile.profile_pic else None
            }
        except (Profile.DoesNotExist, FreelancerProfile.DoesNotExist):
            return obj.user.username if obj.user else None


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'name']
        extra_kwargs = {
            'name': {'help_text': 'Unique category name (e.g., web_dev, ai_training)'}
        }



class JobSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    selected_freelancer = serializers.SerializerMethodField()
    responses = NestedResponseSerializer(many=True, read_only=True)
    
    category = serializers.CharField(write_only=True)
    category_display = serializers.SerializerMethodField(read_only=True)
    
    skills_required = serializers.ListField(child=serializers.CharField(),write_only=True)
    skills_required_display = SkillSerializer(many=True, read_only=True, source='skills_required')
    
    client_rating = serializers.SerializerMethodField()
    client_review_count = serializers.SerializerMethodField()
    client_recent_reviews = serializers.SerializerMethodField()


    class Meta:
        model = Job
        fields = [
            'id', 'client','status','title', 'category', 'category_display', 'description', 'price',
            'posted_date', 'deadline_date',
            'max_freelancers', 'required_freelancers', 'skills_required', 'skills_required_display',
            'preferred_freelancer_level', 'slug',
            'selected_freelancer', 'payment_verified', 'responses',
            'client_rating', 'client_review_count', 'client_recent_reviews'
        ]
        read_only_fields = ['posted_date', 'payment_verified','required_freelancers']
        
        
    def validate_skills_required(self, value):
        skill_objs = []
        for name in value:
            name = name.strip().lower()
            skill, created = Skill.objects.get_or_create(name=name)
            skill_objs.append(skill)
        return skill_objs

    def validate_category(self, value):
        value = value.strip().lower()
        category, created = JobCategory.objects.get_or_create(name=value)
        return category

    def create(self, validated_data):
        category = validated_data.pop('category')
        skills = validated_data.pop('skills_required', [])
        job = Job.objects.create(**validated_data, category=category)
        job.skills_required.set(skills)
        return job

    def update(self, instance, validated_data):
        category = validated_data.pop('category', None)
        skills = validated_data.pop('skills_required', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if category:
            instance.category = category
        instance.save()
        if skills is not None:
            instance.skills_required.set(skills)
        return instance

    def get_category_display(self, obj):
        return obj.category.name if obj.category else None
    
    def get_client_rating(self, obj):
        return round(Review.average_rating_for(obj.client.user), 2)

    def get_client_review_count(self, obj):
        return Review.review_count_for(obj.client.user)

    def get_client_recent_reviews(self, obj):
        recent = Review.recent_reviews_for(obj.client.user, limit=3)
        return ReviewSerializer(recent, many=True).data

    def get_client(self, obj):
        profile = obj.client.user.profile
        if obj.client:
            return {
                'id':obj.client.user.id,
                'first_name': obj.client.user.first_name,
                'last_name': obj.client.user.last_name,
                'username': obj.client.user.username,
                'location': obj.client.user.profile.location,
                #'email': obj.client.user.email,
                'profile_pic': profile.profile_pic.url if profile.profile_pic else None
            }
        return None

    def get_selected_freelancer(self, obj):
        if not obj.selected_freelancer:
            return None
    
        user = obj.selected_freelancer
        rating = round(Review.average_rating_for(user), 2)
        recent_reviews = Review.recent_reviews_for(user)
        return {
            'id': user.id,
            'username': user.username,
            'rating': rating,
            'recent_reviews': ReviewSerializer(recent_reviews, many=True).data
        }
            

class ApplyResponseSerializer(serializers.ModelSerializer):
    cv_url = serializers.SerializerMethodField(read_only=True)
    cover_letter_url = serializers.SerializerMethodField(read_only=True)
    portfolio_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Response
        fields = ['extra_data', 'cv', 'cover_letter', 'portfolio',
                    'cv_url', 'cover_letter_url', 'portfolio_url']
        extra_kwargs = {
            'cv': {'required': False, 'allow_null': True},
            'cover_letter': {'required': False, 'allow_null': True},
            'portfolio': {'required': False, 'allow_null': True}
        }

    def validate_cv(self, value):
        if value:
            validate_file(value, ['.pdf', '.doc', '.docx'])
        return value

    def validate_cover_letter(self, value):
        if value:
            validate_file(value, ['.pdf', '.doc', '.docx'])
        return value

    def validate_portfolio(self, value):
        if value:
            validate_file(
                value, ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'])
        return value

    def get_cv_url(self, obj):
        return obj.cv.url if obj.cv else None

    def get_cover_letter_url(self, obj):
        return obj.cover_letter.url if obj.cover_letter else None

    def get_portfolio_url(self, obj):
        return obj.portfolio.url if obj.portfolio else None


class ResponseListSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    cv_url = serializers.SerializerMethodField()
    cover_letter_url = serializers.SerializerMethodField()
    portfolio_url = serializers.SerializerMethodField()

    class Meta:
        model = Response
        fields = ['id', 'user', 'extra_data', 'submitted_at',
                    'cv_url', 'cover_letter_url', 'portfolio_url','slug']

    def get_user(self, obj):
        profile = getattr(obj.user, 'profile', None)
        return {
            'username': obj.user.username,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'email': obj.user.email,
            'bio': profile.bio if profile else '',
            'location': profile.location if profile else '',
            'profile_pic': profile.profile_pic.url if profile and profile.profile_pic else None,
        }

    def get_cv_url(self, obj):
        return obj.cv.url if obj.cv else None

    def get_cover_letter_url(self, obj):
        return obj.cover_letter.url if obj.cover_letter else None

    def get_portfolio_url(self, obj):
        return obj.portfolio.url if obj.portfolio else None

    def validate_cv(self, value):
        if value:
            validate_file(value, ['.pdf', '.doc', '.docx'])
        return value


    def validate_cover_letter(self, value):
        if value:
            validate_file(value, ['.pdf', '.doc', '.docx'])
        return value


    def validate_portfolio(self, value):
        if value:
            validate_file(value, ['.pdf', '.doc', '.docx',
                        '.jpg', '.jpeg', '.png'])
        return value
        

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
    category = JobCategorySerializer(read_only=True)
    urgency = serializers.SerializerMethodField()
    bookmarked = serializers.SerializerMethodField()
    has_applied = serializers.SerializerMethodField()
    has_applied_and_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'slug', 'category', 'description',
            'price', 'posted_date', 'deadline_date', 'status',
            'client', 'selected_freelancer', 'payment_verified',
            'urgency', 'bookmarked', 'has_applied', 'has_applied_and_bookmarked'
        ]

    def get_urgency(self, obj):
        if obj.deadline_date:
            return (obj.deadline_date - timezone.now()).days <= 2
        return False

    def get_bookmarked(self, obj):
        bookmarked_ids = self.context.get('bookmarked_ids', set())
        return obj.id in bookmarked_ids

    def get_has_applied(self, obj):
        applied_ids = self.context.get('applied_ids', set())
        return obj.id in applied_ids

    def get_has_applied_and_bookmarked(self, obj):
        bookmarked_ids = self.context.get('bookmarked_ids', set())
        applied_ids = self.context.get('applied_ids', set())
        return obj.id in bookmarked_ids and obj.id in applied_ids



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
        fields = ['id', 'chat', 'sender', 'content','is_read',
                    'timestamp', 'is_read', 'is_deleted', 'attachments']
        read_only_fields = ['chat', 'sender',
                            'is_deleted', 'timestamp']

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
