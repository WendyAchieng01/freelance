from django.db.models import Q
from rest_framework import serializers
from django.utils.encoding import force_str
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils.http import urlsafe_base64_decode
from drf_extra_fields.fields import Base64ImageField
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language,PortfolioProject
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from django.contrib.auth import get_user_model
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
from django.contrib.auth.password_validation import validate_password
from accounts.models import Language,ClientProfile
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
from django.urls import reverse
import os


import logging
logger = logging.getLogger(__name__)
User = get_user_model()


class HybridImageField(Base64ImageField):
    """
    Accepts both base64 strings and normal file uploads.
    """

    def to_internal_value(self, data):
        if isinstance(data, InMemoryUploadedFile):
            return data
        return super().to_internal_value(data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Register Example',
            value={
                'username': 'john_doe',
                'email': 'john@gmail.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'password1': 'string12345',
                'password2': 'striing12345',
                'user_type': 'freelancer'
            },
            request_only=True
        )
    ]
)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name','date_joined']
        read_only_fields = ['id']

        
        
class ProfileMiniSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            'user', 'phone', 'location', 'profile_pic', 'bio',
            'pay_id', 'id_card', 'device', 'user_type'
        ]
        read_only_fields = ['pay_id_no']


class RegisterSerializer(serializers.Serializer):
    user = UserSerializer()
    password1 = serializers.CharField(
        write_only=True,
        help_text="Password.",
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        help_text="Confirm password.",
        style={'input_type': 'password'}
    )
    user_type = serializers.ChoiceField(
        choices=[('freelancer', 'Freelancer'), ('client', 'Client')],
        help_text="User type."
    )

    def validate(self, data):
        # Password match check
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(
                {"password2": "Passwords do not match."}
            )

        user_data = data.get('user', {})

        # Unique username check
        if User.objects.filter(username__iexact=user_data.get('username')).exists():
            raise serializers.ValidationError(
                {"user.username": "Username is already taken."}
            )

        # Unique email check
        if User.objects.filter(email__iexact=user_data.get('email')).exists():
            raise serializers.ValidationError(
                {"user.email": "Email is already taken."}
            )

        temp_user = User(
            username=user_data.get('username', ''),
            email=user_data.get('email', '')
        )
        validate_password(data['password1'], temp_user)

        return data

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        password = validated_data.pop('password1')

        user = User.objects.create_user(
            username=user_data['username'].lower(),
            email=user_data['email'].lower(),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', ''),
            password=password,
            is_active=False
        )

        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={'user_type': validated_data['user_type']}
        )
        if not created:
            profile.user_type = validated_data['user_type']
            profile.save()

        return user


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Login Example',
            value={'username': 'john','password': 'string12345'},
            request_only=True
        )
    ]
)
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email.")
    password = serializers.CharField(write_only=True, help_text="Password.")
    remember_me = serializers.BooleanField(default=False, required=False)
    
    def validate(self, data):
        username = data.get('username', '').lower()
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Both fields are required.")

        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"message": "Invalid username or email."}
            )

        if not user.is_active:
            # Build full URL using request
            request = self.context.get('request')
            resend_path = reverse('resend-verification')

            if request:
                base_url = request.build_absolute_uri(resend_path)

            else:
                # Fallback to domain defined in settings
                fallback_domain = getattr(settings, 'FRONTEND_URL', '')
                base_url = f'http://{fallback_domain}{resend_path}'

            raise serializers.ValidationError({
                "message": [
                    "Account is disabled. Please verify your email to activate.",
                ]
            })

        user = authenticate(username=user.username, password=password)
        if not user:
            logger.warning(f"Authentication failed for user: {username}")
            raise serializers.ValidationError({
                "message": "Invalid credentials. Check your username or password."
            })

        data['user'] = user
        data['remember_me'] = data.get('remember_me', False)
        return data



class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="JWT refresh token")


class PasswordChangeSerializer(serializers.Serializer):
    uid = serializers.CharField(
        write_only=True, help_text="Base64 encoded user ID from the reset link.")
    token = serializers.CharField(
        write_only=True, help_text="Password reset token from the reset link.")
    new_password1 = serializers.CharField(
        write_only=True,
        help_text="New password.",
        style={'input_type': 'password'}
    )
    new_password2 = serializers.CharField(
        write_only=True,
        help_text="Confirm new password.",
        style={'input_type': 'password'}
    )

    def validate(self, data):
        # Ensure passwords match
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError(
                {"new_password2": "Passwords do not match."}
            )

        # Validate password strength
        validate_password(data['new_password1'], self.context.get('user'))

        return data



class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Email for password reset.")


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True, help_text="New password.")

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(
        help_text="Registered email address for verification."
    )


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField(
        help_text="Base64 encoded user ID from the verification link.")
    token = serializers.CharField(
        help_text="Verification token from the verification link.")

    def validate(self, attrs):
        uidb64 = attrs.get("uid")
        token = attrs.get("token")

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, User.DoesNotExist):
            raise serializers.ValidationError(
                {"error": "Invalid verification link."})

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(
                {"error": "Invalid or expired token."})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.is_active = True
        user.save()

        refresh = RefreshToken.for_user(user)
        return {
            "message": "Email verified.",
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }
        

class ProfileSerializer(serializers.ModelSerializer):
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            'phone', 'location', 'bio', 'profile_pic',
            'pay_id', 'id_card', 'user_type'
        ]
        read_only_fields = ['user', 'user_type','pay_id_no',
                            'date_modified', 'email_verified', 'device']

    def validate_pay_id(self, value):
        valid_choices = [choice[0]
                         for choice in Profile._meta.get_field('pay_id').choices]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"{value} is not a valid choice.")
        return value

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            instance.device = user_agent

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'help_text': 'Skill name (e.g., Python, Django).'}}


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'name']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'help_text': 'Language name (e.g., English, Swahili).'}}


class PortfolioProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioProject
        fields = [
            "id","freelancer","project_title","role","description",
            "link","slug","project_media","created_at",
        ]
        read_only_fields = ["id", "freelancer", "slug", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        # Auto-set freelancer from the user’s profile (if exists)
        freelancer_profile = getattr(user.profile, "freelancer_profile", None)
        validated_data["freelancer"] = freelancer_profile
        validated_data["user"] = user
        return super().create(validated_data)


#freelance profile form
class PortfolioProjectReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioProject
        fields = [
            'slug','project_title','role','description','link',
            'project_media',
            'created_at',
        ]
        read_only_fields = fields


class FreelancerProfileReadSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    languages = serializers.StringRelatedField(many=True)
    skills = serializers.StringRelatedField(many=True)
    full_name = serializers.SerializerMethodField()

    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()

    portfolio_projects = serializers.SerializerMethodField()
    profile_pic = serializers.ImageField(required=False, allow_null=True)
    
    

    class Meta:
        model = FreelancerProfile
        fields = [
            'id', 'full_name', 'profile', 'experience_years','profile_pic',
            'hourly_rate', 'portfolio_link', 'availability', 'languages',
            'skills', 'is_visible', 'slug',
            'rating', 'review_count', 'recent_reviews',
            'portfolio_projects', 
        ]

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name()

    def get_rating(self, obj):
        return round(Review.average_rating_for(obj.profile.user), 2)

    def get_review_count(self, obj):
        return Review.review_count_for(obj.profile.user)

    def get_recent_reviews(self, obj):
        from api.core.serializers import ReviewSerializer
        
        reviews = Review.recent_reviews_for(obj.profile.user, limit=3)
        return ReviewSerializer(reviews, many=True).data

    def get_portfolio_projects(self, obj):
        """Return up to 4 portfolio projects for this freelancer."""
        projects = PortfolioProject.objects.filter(user=obj.profile.user)[:4]
        return PortfolioProjectReadSerializer(projects, many=True).data


class ProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            'phone', 'location', 'profile_pic', 'bio',
            'pay_id', 'id_card', 'device'
        ]


class FreelancerProfileWriteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="profile.user.username", required=False)
    first_name = serializers.CharField(
        source="profile.user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(
        source="profile.user.last_name", required=False, allow_blank=True)
    email = serializers.EmailField(source="profile.user.email", required=False)

    phone = serializers.CharField(
        source="profile.phone", required=False, allow_blank=True)
    location = serializers.CharField(
        source="profile.location", required=False, allow_blank=True)
    bio = serializers.CharField(
        source="profile.bio", required=False, allow_blank=True)
    profile_picture = serializers.ImageField(
        source="profile.profile_pic", required=False, allow_null=True)
    profile_pic = serializers.ImageField(required=False, allow_null=True)

    skills = serializers.ListField(
        child=serializers.CharField(), required=False)
    languages = serializers.ListField(
        child=serializers.CharField(), required=False)

    class Meta:
        model = FreelancerProfile
        fields = [
            "first_name", "last_name", "email", "username",
            "phone", "location", "bio", "profile_picture","profile_pic",
            "skills", "languages", "experience_years", "hourly_rate",
            "availability", "is_visible"
        ]

    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {})
        user_data = profile_data.pop("user", {})
        skills = validated_data.pop("skills", [])
        languages = validated_data.pop("languages", [])

        user = self.context["request"].user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.user_type = "freelancer"
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        freelancer = FreelancerProfile.objects.create(
            profile=profile, **validated_data)

        skill_objs = [Skill.objects.get_or_create(
            name=skill)[0] for skill in skills]
        language_objs = [Language.objects.get_or_create(
            name=lang)[0] for lang in languages]

        freelancer.skills.set(skill_objs)
        freelancer.languages.set(language_objs)

        return freelancer

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        user_data = profile_data.pop("user", {})
        skills = validated_data.pop("skills", [])
        languages = validated_data.pop("languages", [])

        user = instance.profile.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        profile = instance.profile
        profile.user_type = "freelancer"
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if skills:
            skill_objs = [Skill.objects.get_or_create(
                name=skill)[0] for skill in skills]
            instance.skills.set(skill_objs)

        if languages:
            language_objs = [Language.objects.get_or_create(
                name=lang)[0] for lang in languages]
            instance.languages.set(language_objs)

        return instance


class FreelancerListSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    languages = LanguageSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    email = serializers.EmailField(source='profile.user.email')
    phone_number = serializers.CharField(source='profile.phone')
    location = serializers.CharField(source='profile.location')

    class Meta:
        model = FreelancerProfile
        fields = [
            'profile',
            'email',
            'phone_number',
            'location',
            'languages',
            'skills',
        ]



class ClientProfileReadSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    languages = serializers.StringRelatedField(many=True)
    full_name = serializers.SerializerMethodField()
    
    rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = [
            'id','full_name','profile','company_name',
            'company_website','industry','project_budget','preferred_freelancer_level',
            'languages',
            'slug',
            'is_verified', 'rating', 'review_count', 'recent_reviews'
        ]

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name()
    
    def get_rating(self, obj):
        return round(Review.average_rating_for(obj.profile.user), 2)

    def get_review_count(self, obj):
        return Review.review_count_for(obj.profile.user)

    def get_recent_reviews(self, obj):
        from api.core.serializers import ReviewSerializer
        
        reviews = Review.recent_reviews_for(obj.profile.user, limit=3)
        return ReviewSerializer(reviews, many=True).data


class ClientProfileWriteSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="profile.user.username", required=False)
    first_name = serializers.CharField(
        source="profile.user.first_name", required=False, allow_blank=True)
    last_name = serializers.CharField(
        source="profile.user.last_name", required=False, allow_blank=True)
    email = serializers.EmailField(source="profile.user.email", required=False)

    phone = serializers.CharField(
        source="profile.phone", required=False, allow_blank=True)
    location = serializers.CharField(
        source="profile.location", required=False, allow_blank=True)
    bio = serializers.CharField(
        source="profile.bio", required=False, allow_blank=True)
    pay_id = serializers.CharField(
        source="profile.pay_id", required=False, allow_blank=True)
    id_card = serializers.CharField(
        source="profile.id_card", required=False, allow_blank=True)
    profile_picture = serializers.ImageField(
        source="profile.profile_pic", required=False, allow_null=True)

    languages = serializers.ListField(
        child=serializers.CharField(), required=False)

    class Meta:
        model = ClientProfile
        fields = [
            "username", "first_name", "last_name", "email",
            "phone", "location", "bio", "pay_id", "id_card", "profile_picture",
            "company_name", "company_website", "industry", "project_budget",
            "preferred_freelancer_level", "languages",
        ]
        read_only_fields = ["pay_id_no",]

    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {})
        user_data = profile_data.pop("user", {})
        languages = validated_data.pop("languages", [])

        user = self.context["request"].user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.user_type = "client"
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        client = ClientProfile.objects.create(
            profile=profile, **validated_data)

        if languages:
            language_objs = [Language.objects.get_or_create(
                name=lang)[0] for lang in languages]
            client.languages.set(language_objs)

        return client

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        user_data = profile_data.pop("user", {})
        languages = validated_data.pop("languages", [])

        profile = instance.profile
        user = profile.user

        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.user_type = "client"
        profile.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if languages:
            language_objs = [Language.objects.get_or_create(
                name=lang)[0] for lang in languages]
            instance.languages.set(language_objs)

        return instance



class ClientListSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    languages = LanguageSerializer(many=True, read_only=True)
    email = serializers.EmailField(source='profile.user.email')
    phone = serializers.CharField(source='profile.phone', allow_blank=True)
    location = serializers.CharField(
        source='profile.location', allow_blank=True)

    class Meta:
        model = ClientProfile
        fields = [
            'id',
            'profile',
            'company_name',
            'industry',
            'project_budget',
            'preferred_freelancer_level',
            'is_verified',
            'slug',
            'email',
            'phone',
            'location',
            'languages',
        ]


class AuthUserSerializer(serializers.ModelSerializer):
    profile_data = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'profile_data',
        ]

    def get_profile_data(self, obj):
        try:
            profile = obj.profile
            if profile.user_type == 'freelancer' and hasattr(profile, 'freelancer_profile'):
                return {
                    'freelancer_profile': FreelancerProfileReadSerializer(
                        profile.freelancer_profile, context=self.context
                    ).data
                }
            elif profile.user_type == 'client' and hasattr(profile, 'client_profile'):
                return {
                    'client_profile': ClientProfileReadSerializer(
                        profile.client_profile, context=self.context
                    ).data
                }
        except Profile.DoesNotExist:
            self._fallback_user_data(obj)

        # base user info only
        return self._fallback_user_data(obj)

    def _fallback_user_data(self, obj):
        return {
            "id": obj.id,
            "username": obj.username,
            "email": obj.email,
            "first_name": obj.first_name,
            "last_name": obj.last_name
        }
