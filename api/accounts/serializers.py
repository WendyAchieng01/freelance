from django.db.models import Q
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from django.contrib.auth import get_user_model
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
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
        # Use Q to query username OR email
        user = User.objects.filter(
            Q(username=identifier) | Q(email=identifier)).first()
        if not user:
            raise serializers.ValidationError(
                {"identifier": "Invalid username or email."})
        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError(
                {"password": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "Account not verified."})
        data['user'] = user
        return data


class PasswordChangeSerializer(serializers.Serializer):
    new_password1 = serializers.CharField(
        write_only=True, help_text="New password.")
    new_password2 = serializers.CharField(
        write_only=True, help_text="Confirm new password.")

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError(
                {"new_password2": "Passwords do not match."})
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Email for password reset.")


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField(help_text="Encoded user ID.")
    token = serializers.CharField(help_text="Password reset token.")
    new_password = serializers.CharField(
        write_only=True, help_text="New password.")


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


class FreelancerProfileSerializer(serializers.ModelSerializer):
    skills = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )
    languages = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        write_only=True,
        source='skills',
        help_text="List of skill IDs."
    )
    language_ids = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(),
        many=True,
        write_only=True,
        source='languages',
        help_text="List of language IDs."
    )

    class Meta:
        model = FreelancerProfile
        fields = ['id', 'portfolio_link', 'experience_years', 'hourly_rate','availability', 'skills', 'languages', 'skill_ids', 'language_ids']
        read_only_fields = ['id']
        extra_kwargs = {
            'portfolio_link': {'help_text': 'Portfolio URL (optional).'},
            'experience_years': {'help_text': 'Years of experience.'},
            'hourly_rate': {'help_text': 'Hourly rate in USD.'},
            'availability': {'help_text': 'Availability (e.g., full_time, part_time).'},
        }


class ClientProfileSerializer(serializers.ModelSerializer):
    languages = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name'
    )
    language_ids = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(),
        many=True,
        write_only=True,
        source='languages',
        help_text="List of language IDs."
    )

    class Meta:
        model = ClientProfile
        fields = ['id', 'company_name', 'company_website', 'industry','project_budget', 'preferred_freelancer_level', 'languages', 'language_ids']
        read_only_fields = ['id']
        extra_kwargs = {
            'company_name': {'help_text': 'Company or client name.'},
            'company_website': {'help_text': 'Company website (optional).'},
            'industry': {'help_text': 'Client industry.'},
            'project_budget': {'help_text': 'Project budget in USD.'},
            'preferred_freelancer_level': {'help_text': 'Preferred freelancer level.'},
        }


class FreelancerFormSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, help_text="Full name.")
    email = serializers.EmailField(help_text="Email address.")
    phone_number = serializers.CharField(max_length=20, help_text="Phone number.")
    experience_years = serializers.IntegerField(min_value=0, help_text="Years of experience.")
    hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, help_text="Hourly rate in USD.")
    languages = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all(), many=True, help_text="Language IDs.")
    photo = serializers.ImageField(required=False, help_text="Profile photo (optional).")
    id_number = serializers.CharField(max_length=20, required=False, help_text="ID number (optional).")
    location = serializers.CharField(max_length=100, required=False, help_text="Location (optional).")
    pay_id = serializers.ChoiceField(choices=[('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')], required=False, help_text="Payment method.")
    pay_id_no = serializers.CharField(max_length=20, help_text="Payment ID number.")
    skills = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all(), many=True, help_text="Skill IDs.")
    portfolio_link = serializers.URLField(required=False, help_text="Portfolio URL (optional).")
    availability = serializers.ChoiceField(choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'),('weekends', 'Weekends Only'), ('custom', 'Custom Schedule')
    ], required=False, help_text="Availability.")

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email is already taken.")
        return value

    def save(self, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.user_type = 'freelancer'
        profile.phone = self.validated_data.get('phone_number', '')
        profile.location = self.validated_data.get('location', '')
        profile.profile_pic = self.validated_data.get('photo')
        profile.pay_id = self.validated_data.get('pay_id', 'M-Pesa')
        profile.pay_id_no = self.validated_data.get('pay_id_no', '')
        profile.id_card = self.validated_data.get('id_number', '')
        profile.save()

        user.email = self.validated_data.get('email', user.email)
        user.save()

        freelancer_profile, _ = FreelancerProfile.objects.get_or_create(profile=profile)
        freelancer_profile.portfolio_link = self.validated_data.get('portfolio_link', '')
        freelancer_profile.experience_years = self.validated_data.get('experience_years', 0)
        freelancer_profile.hourly_rate = self.validated_data.get('hourly_rate', 0)
        freelancer_profile.availability = self.validated_data.get('availability', '')
        freelancer_profile.save()

        freelancer_profile.skills.set(self.validated_data.get('skills', []))
        freelancer_profile.languages.set(self.validated_data.get('languages', []))
        return user


class ClientFormSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=100, help_text="Company or client name.")
    email = serializers.EmailField(help_text="Email address.")
    phone_number = serializers.CharField(max_length=20, help_text="Phone number.")
    industry = serializers.ChoiceField(choices=ClientProfile.INDUSTRY_CHOICES, help_text="Industry.")
    languages = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all(), many=True, help_text="Language IDs.")
    location = serializers.CharField(max_length=100, required=False, help_text="Location (optional).")
    pay_id = serializers.ChoiceField(choices=[('M-Pesa', 'M-Pesa'), ('Binance', 'Binance')], required=False, help_text="Payment method.")
    pay_id_no = serializers.CharField(max_length=20, required=False, help_text="Payment ID number.")
    company_website = serializers.URLField(required=False, help_text="Company website (optional).")
    project_budget = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, help_text="Project budget in USD.")
    preferred_freelancer_level = serializers.ChoiceField(choices=[('entry', 'Entry Level'), ('intermediate','Intermediate'), ('expert', 'Expert')
    ], required=False, help_text="Preferred freelancer level.")

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email is already taken.")
        return value

    def save(self, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.user_type = 'client'
        profile.phone = self.validated_data.get('phone_number', '')
        profile.location = self.validated_data.get('location', '')
        profile.pay_id = self.validated_data.get('pay_id', 'M-Pesa')
        profile.pay_id_no = self.validated_data.get('pay_id_no', '')
        profile.save()

        user.email = self.validated_data.get('email', user.email)
        user.save()

        client_profile, _ = ClientProfile.objects.get_or_create(
            profile=profile)
        client_profile.company_name = self.validated_data.get(
            'company_name', user.username)
        client_profile.industry = self.validated_data.get('industry', '')
        client_profile.project_budget = self.validated_data.get(
            'project_budget', 0)
        client_profile.preferred_freelancer_level = self.validated_data.get(
            'preferred_freelancer_level', '')
        client_profile.company_website = self.validated_data.get(
            'company_website', '')
        client_profile.save()

        client_profile.languages.set(self.validated_data.get('languages', []))
        return user
