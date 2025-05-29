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

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Register Example',
            value={
                'username': 'john_doe',
                'email': 'john@example.com',
                'password1': 'securepassword123',
                'password2': 'securepassword123',
                'user_type': 'freelancer'
            },
            request_only=True
        )
    ]
)
class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150, help_text="Unique username.")
    email = serializers.EmailField(help_text="Unique email address.")
    password1 = serializers.CharField(
        write_only=True, help_text="Password (minimum 8 characters).")
    password2 = serializers.CharField(
        write_only=True, help_text="Confirm password.")
    user_type = serializers.ChoiceField(choices=[(
        'freelancer', 'Freelancer'), ('client', 'Client')], help_text="User type.")

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(
                {"password2": "Passwords do not match."})
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError(
                {"username": "Username is already taken."})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError(
                {"email": "Email is already taken."})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password1'],
            is_active=False
        )
        # Use get_or_create to avoid duplicate Profile
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={'user_type': validated_data['user_type']}
        )
        if not created:
            # Profile already exists; update user_type if needed
            profile.user_type = validated_data['user_type']
            profile.save()
        return user


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Login Example',
            value={'identifier': 'john@example.com','password': 'securepassword123'},
            request_only=True
        )
    ]
)
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Username or email.")
    password = serializers.CharField(write_only=True, help_text="Password.")

    def validate(self, data):
        identifier = data.get('identifier')
        password = data.get('password')

        if not identifier or not password:
            raise serializers.ValidationError("Both fields are required.")

        try:
            user = User.objects.get(
                Q(username=identifier) | Q(email=identifier))
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"identifier": "Invalid username or email."})

        user = authenticate(username=user.username, password=password)

        if not user:
            raise serializers.ValidationError(
                {"password": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": ["Account is disabled."]})

        data['user'] = user
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
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'user', 'phone', 'location', 'bio','profile_pic', 'pay_id', 'pay_id_no', 'id_card', 'user_type']
        read_only_fields = ['id', 'user', 'user_type']
        extra_kwargs = {
            'phone': {'help_text': 'Phone number.'},
            'location': {'help_text': 'Location (optional).'},
            'bio': {'help_text': 'Biography (optional).'},
            'profile_pic': {'help_text': 'Profile picture (optional).'},
            'pay_id': {'help_text': 'Payment method (M-Pesa or Binance).'},
            'pay_id_no': {'help_text': 'Payment ID number.'},
            'id_card': {'help_text': 'ID card number (optional).'},
            'user_type': {'help_text': 'User type (freelancer or client).'},
        }


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


class FreelancerFormSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='profile.user.email')
    phone_number = serializers.CharField(source='profile.phone')
    location = serializers.CharField(source='profile.location', required=False)
    pay_id = serializers.ChoiceField(
        choices=[('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')],
        source='profile.pay_id', required=False
    )
    pay_id_no = serializers.CharField(
        source='profile.pay_id_no', required=False)
    profile_pic = serializers.URLField(
        source='profile.profile_pic', required=False)
    id_number = serializers.CharField(source='profile.id_card', required=False)
    full_name = serializers.SerializerMethodField()
    languages = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(), many=True)
    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), many=True, required=False)

    class Meta:
        model = FreelancerProfile
        fields = [
            'full_name', 'email', 'phone_number', 'location', 'pay_id', 'pay_id_no',
            'profile_pic', 'id_number', 'experience_years', 'hourly_rate',
            'portfolio_link', 'availability', 'languages', 'skills'
        ]

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name()

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email is already taken.")
        return value

    def create(self, validated_data):
        return self._create_or_update(validated_data)

    def update(self, instance, validated_data):
        return self._create_or_update(validated_data, instance)

    def _create_or_update(self, validated_data, instance=None):
        user = self.context['request'].user
        profile_data = validated_data.pop('profile', {})

        email = profile_data.get('user', {}).get('email', user.email)
        phone = profile_data.get('phone', '')
        location = profile_data.get('location', '')
        pay_id = profile_data.get('pay_id', '')
        pay_id_no = profile_data.get('pay_id_no', '')
        profile_pic = profile_data.get('profile_pic', '')
        id_number = profile_data.get('id_card', '')

        user.email = email
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.location = location
        profile.pay_id = pay_id
        profile.pay_id_no = pay_id_no
        profile.profile_pic = profile_pic
        profile.id_card = id_number
        profile.user_type = 'freelancer'
        profile.save()

        languages = validated_data.pop('languages', [])
        skills = validated_data.pop('skills', [])

        freelancer_profile = instance or FreelancerProfile(profile=profile)
        for attr, value in validated_data.items():
            setattr(freelancer_profile, attr, value)
        freelancer_profile.save()

        if languages:
            freelancer_profile.languages.set(languages)
        if skills:
            freelancer_profile.skills.set(skills)

        return freelancer_profile

class ClientFormSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='profile.user.email')
    phone_number = serializers.CharField(source='profile.phone')
    location = serializers.CharField(
        source='profile.location', allow_blank=True, required=False)
    pay_id = serializers.ChoiceField(choices=[(
        'M-Pesa', 'M-Pesa'), ('Binance', 'Binance')], source='profile.pay_id', required=False, allow_blank=True)
    pay_id_no = serializers.CharField(
        source='profile.pay_id_no', allow_blank=True, required=False)
    languages = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(), many=True)

    class Meta:
        model = ClientProfile
        fields = [
            'company_name',
            'email',
            'phone_number',
            'industry',
            'languages',
            'location',
            'pay_id',
            'pay_id_no',
            'company_website',
            'project_budget',
            'preferred_freelancer_level',
        ]

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email is already taken.")
        return value

    def update(self, instance, validated_data):
        # Update nested profile fields
        profile_data = validated_data.pop('profile', {})
        user_data = profile_data.pop(
            'user', {}) if 'user' in profile_data else {}

        # Update user email if present
        email = user_data.get('email')
        if email:
            instance.profile.user.email = email
            instance.profile.user.save()

        # Update profile fields
        for attr, value in profile_data.items():
            setattr(instance.profile, attr, value)
        instance.profile.save()

        # Update ClientProfile fields
        for attr, value in validated_data.items():
            if attr != 'languages':  # Handle languages separately
                setattr(instance, attr, value)
        instance.save()

        # Correct way to update many-to-many field
        if 'languages' in validated_data:
            instance.languages.set(validated_data['languages'])

        return instance

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        user_data = profile_data.pop(
            'user', {}) if 'user' in profile_data else {}

        user = self.context['request'].user
        # Update user email if present
        email = user_data.get('email')
        if email:
            user.email = email
            user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.user_type = 'client'
        profile.save()

        client_profile, created = ClientProfile.objects.get_or_create(
            profile=profile)
        for attr, value in validated_data.items():
            if attr != 'languages':
                setattr(client_profile, attr, value)
        client_profile.save()

        if 'languages' in validated_data:
            client_profile.languages.set(validated_data['languages'])

        return client_profile



class ClientListSerializer(serializers.ModelSerializer):
    languages = LanguageSerializer(many=True)
    email = serializers.EmailField(source='profile.user.email')
    phone_number = serializers.CharField(source='profile.phone')
    location = serializers.CharField(source='profile.location')

    class Meta:
        model = ClientProfile
        fields = [
            'company_name',
            'email',
            'phone_number',
            'industry',
            'languages',
            'location',
            'company_website',
            'project_budget',
            'preferred_freelancer_level',
        ]
