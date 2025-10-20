from rest_framework import serializers
from django.contrib.auth import get_user_model
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from accounts.models import Profile

User = get_user_model()


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)
    user_type = serializers.ChoiceField(
        choices=[('freelancer', 'Freelancer'), ('client', 'Client')],
        required=True
    )

    def validate(self, attrs):
        token = attrs.get('id_token')
        user_type = attrs.get('user_type')

        # Local testing bypass for development only
        if settings.DEBUG and token == "test":
            email = "testuser@example.com"
            name = "Test User"
        else:
            # --- Normal Google verification ---
            try:
                id_info = id_token.verify_oauth2_token(
                    token, requests.Request(), settings.GOOGLE_CLIENT_ID
                )
                email = id_info.get('email')
                name = id_info.get('name', '')
            except Exception:
                raise serializers.ValidationError(
                    {'error': 'Invalid or expired Google token.'})

        # --- Extract name parts ---
        first_name, *last_name_parts = name.split(' ', 1)
        last_name = last_name_parts[0] if last_name_parts else ''

        if not email:
            raise serializers.ValidationError(
                {'error': 'Google account missing email.'})

        # --- Create or get user ---
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True
            }
        )

        # --- Create or get profile ---
        Profile.objects.get_or_create(
            user=user,
            defaults={'user_type': user_type}
        )

        attrs['user'] = user
        attrs['created'] = created
        return attrs
