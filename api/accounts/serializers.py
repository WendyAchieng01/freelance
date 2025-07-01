from django.db.models import Q
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from django.contrib.auth import get_user_model
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
from django.contrib.auth.password_validation import validate_password
from accounts.models import Language,ClientProfile
import os


import logging
logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Register Example',
            value={
                'username': 'john_doe',
                'email': 'john@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'password1': 'securepassword123',
                'password2': 'securepassword123',
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

    class Meta:
        model = Profile
        fields = [
            'user', 'phone', 'location', 'profile_pic', 'bio',
            'pay_id', 'pay_id_no', 'id_card', 'device', 'user_type'
        ]


class RegisterSerializer(serializers.Serializer):
    user = UserSerializer()
    password1 = serializers.CharField(write_only=True, help_text="Password.")
    password2 = serializers.CharField(
        write_only=True, help_text="Confirm password.")
    user_type = serializers.ChoiceField(
        choices=[('freelancer', 'Freelancer'), ('client', 'Client')],
        help_text="User type."
    )

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(
                {"password2": "Passwords do not match."})

        user_data = data.get('user', {})
        if User.objects.filter(username=user_data.get('username')).exists():
            raise serializers.ValidationError(
                {"user.username": "Username is already taken."})
        if User.objects.filter(email=user_data.get('email')).exists():
            raise serializers.ValidationError(
                {"user.email": "Email is already taken."})

        return data

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        password = validated_data.pop('password1')

        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
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
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Both fields are required.")

        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"identifier": "Invalid username or email."}
            )

        user = authenticate(username=user.username, password=password)

        if not user:
            logger.warning(f"Authentication failed for user: {username}")
            raise serializers.ValidationError(
                {"password": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": ["Account is disabled."]}
            )

        data['user'] = user
        # ensure remember_me is returned with validated_data
        data['remember_me'] = data.get('remember_me', False)
        return data



class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="JWT refresh token")



class PasswordChangeSerializer(serializers.Serializer):
    new_password1 = serializers.CharField(
        write_only=True, help_text="New password.")
    new_password2 = serializers.CharField(
        write_only=True, help_text="Confirm new password.")

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError(
                {"new_password2": "Passwords do not match."})
            validate_password(data['new_password1']
                )
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


class ProfileSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    profile_pic = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = Profile
        fields = '__all__'
        read_only_fields = ['user', 'user_type','date_modified','email_verified','device']
        
    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            validated_data['device'] = user_agent
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            instance.device = user_agent
        return super().update(instance, validated_data)



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


#freelance profile form


class FreelancerProfileReadSerializer(serializers.ModelSerializer):
    profile = ProfileMiniSerializer()
    languages = serializers.StringRelatedField(many=True)
    skills = serializers.StringRelatedField(many=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = FreelancerProfile
        fields = [
            'id',
            'full_name',
            'profile',
            'experience_years',
            'hourly_rate',
            'portfolio_link',
            'availability',
            'languages',
            'skills',
            'is_visible',
            'slug'
        ]

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name()


class ProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            'phone', 'location', 'profile_pic', 'bio',
            'pay_id', 'pay_id_no', 'id_card', 'device'
        ]


class FreelancerProfileWriteSerializer(serializers.ModelSerializer):
    profile = ProfileWriteSerializer()
    languages = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all(), many=True)
    skills = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True, required=False)

    class Meta:
        model = FreelancerProfile
        fields = [
            'profile',
            'experience_years',
            'hourly_rate',
            'availability',
            'languages',
            'skills',
            'is_visible'
        ]

    def update_nested_profile(self, profile, profile_data):
        for field in profile_data:
            setattr(profile, field, profile_data[field])
        profile.user_type = 'freelancer'
        profile.save()

    def create(self, validated_data):
        return self._create_or_update(validated_data)

    def update(self, instance, validated_data):
        return self._create_or_update(validated_data, instance)

    def _create_or_update(self, validated_data, instance=None):
        # Pop nested and many-to-many fields from validated_data
        profile_data = validated_data.pop('profile', {})
        languages = validated_data.pop('languages', [])
        skills = validated_data.pop('skills', [])

        # Get or create the user’s profile
        user = self.context['request'].user
        profile, _ = Profile.objects.get_or_create(user=user)
        self.update_nested_profile(profile, profile_data)

        # Create or use existing FreelancerProfile instance
        freelancer = instance or FreelancerProfile(profile=profile)

        # Set direct fields only
        for attr, value in validated_data.items():
            setattr(freelancer, attr, value)

        # Save the instance
        freelancer.save()

        # Set many-to-many fields if provided
        if languages:
            freelancer.languages.set(languages)
        if skills:
            freelancer.skills.set(skills)

        return freelancer



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

    class Meta:
        model = ClientProfile
        fields = [
            'id',
            'full_name',
            'profile',
            'company_name',
            'company_website',
            'industry',
            'project_budget',
            'preferred_freelancer_level',
            'languages',
            'slug',
            'is_verified',
        ]

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name()


class ClientProfileWriteSerializer(serializers.ModelSerializer):
    profile = ProfileWriteSerializer()
    languages = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(), many=True, required=False
    )

    class Meta:
        model = ClientProfile
        fields = [
            'profile',
            'company_name',
            'company_website',
            'industry',
            'project_budget',
            'preferred_freelancer_level',
            'languages',
            'is_verified',
        ]

    def update_nested_profile(self, profile, profile_data):
        for field in profile_data:
            setattr(profile, field, profile_data[field])
        profile.user_type = 'client'
        profile.save()

    def create(self, validated_data):
        return self._create_or_update(validated_data)

    def update(self, instance, validated_data):
        return self._create_or_update(validated_data, instance)

    def _create_or_update(self, validated_data, instance=None):
        # Pop nested and many-to-many fields from validated_data
        profile_data = validated_data.pop('profile', {})
        languages = validated_data.pop('languages', [])

        # Get or create the user’s profile
        user = self.context['request'].user
        profile, _ = Profile.objects.get_or_create(user=user)
        self.update_nested_profile(profile, profile_data)

        # Create or use existing ClientProfile instance
        client = instance or ClientProfile(profile=profile)

        # Set direct fields only
        for attr, value in validated_data.items():
            setattr(client, attr, value)

        # Save the instance
        client.save()

        # Set many-to-many fields if provided
        if languages:
            client.languages.set(languages)

        return client


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
    freelancer_profile = serializers.SerializerMethodField()
    client_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'freelancer_profile', 'client_profile']

    def get_freelancer_profile(self, obj):
        try:
            if hasattr(obj.profile, 'freelancer_profile'):
                return FreelancerProfileReadSerializer(obj.profile.freelancer_profile, context=self.context).data
        except:
            return None

    def get_client_profile(self, obj):
        try:
            if hasattr(obj.profile, 'client_profile'):
                return ClientProfileReadSerializer(obj.profile.client_profile, context=self.context).data
        except:
            return None
