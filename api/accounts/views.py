from rest_framework.views import APIView
from rest_framework import viewsets, status, permissions,generics,filters
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken,TokenError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.parsers import JSONParser
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.permissions import AllowAny,IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.utils.html import format_html
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.http import FileResponse, Http404
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from core.models import Job, Response as CoreResponse, Chat, Message, MessageAttachment, Review
from .permissions import IsOwnerOrAdmin,IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, CanReview,IsFreelancerOrAdminOrClientReadOnly,IsClientOrAdminFreelancerReadOnly

from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,LogoutSerializer,
    PasswordChangeSerializer, PasswordResetRequestSerializer,ResendVerificationSerializer,
    PasswordResetConfirmSerializer, ProfileSerializer, SkillSerializer,
    LanguageSerializer,ClientListSerializer,FreelancerListSerializer,
    FreelancerFormSerializer, ClientFormSerializer
)

User = get_user_model()


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user == request.user


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    @extend_schema(
        description="List or create users (admin only for listing).",
        responses={200: UserSerializer(many=True), 201: UserSerializer}
    )
    def list(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve user details.",
        responses={200: UserSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=UserSerializer,
        description="Update user details (owner or admin only).",
        responses={200: UserSerializer, 400: OpenApiResponse(
            description="Invalid input.")}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete user account (owner or admin only).",
        responses={204: OpenApiResponse(description="User deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User created, verification email sent."),
            400: OpenApiResponse(description="Invalid input.")
        },
        description="Register a new user and send verification email."
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            current_site = get_current_site(request)
            verification_url = f'http://{current_site.domain}/api/v1/accounts/verify-email/{uid}/{token}/'

            subject = 'Verify Your Email Address'
            message_text = f'Hi {user.username},\n\nPlease click the link to verify your email: {verification_url}'
            message_html = format_html(
                '<div style="font-family: Arial, sans-serif; text-align: center;">'
                f'<h2>Welcome, {user.username}!</h2>'
                '<p>Please click the button below to verify your email address:</p>'
                f'<a href="{verification_url}" style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">'
                'Verify Email</a><p>If you didn\'t sign up, ignore this email.</p>'
                '</div>'
            )
            email = EmailMultiAlternatives(
                subject, message_text, 'info@nilltechsolutions.com', [user.email])
            email.attach_alternative(message_html, "text/html")
            email.send()

            return Response({"message": "User created, verification email sent."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Email verified, JWT tokens returned."),
            400: OpenApiResponse(description="Invalid or expired token.")
        },
        description="Verify user email with token."
    )
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if default_token_generator.check_token(user, token):
                user.is_active = True
                user.save()
                refresh = RefreshToken.for_user(user)
                return Response({
                    "message": "Email verified.",
                    "access": str(refresh.access_token),
                    "refresh": str(refresh)
                }, status=status.HTTP_200_OK)
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError, User.DoesNotExist):
            return Response({"error": "Invalid verification link."}, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=ResendVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Verification email resent."),
            400: OpenApiResponse(description="User not found or already verified.")
        },
        description="Resend verification email to a registered user."
    )
    def post(self, request):
        # If user is authenticated, prioritize their ID
        if request.user and request.user.is_authenticated:
            user = request.user
        else:
            serializer = ResendVerificationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "No user with this email found."}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({"error": "Account is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate verification token and link
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        current_site = get_current_site(request)
        verification_url = f'http://{current_site.domain}/api/v1/accounts/verify-email/{uid}/{token}/'

        # Email content
        subject = 'Verify Your Email Address'
        message_text = f'Hi {user.username},\n\nPlease click the link to verify your email: {verification_url}'
        message_html = format_html(
            '<div style="font-family: Arial, sans-serif; text-align: center;">'
            f'<h2>Hi {user.username},</h2>'
            '<p>Please click the button below to verify your email address:</p>'
            f'<a href="{verification_url}" style="display: inline-block; background-color: #007bff; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">'
            'Verify Email</a><p>This link will expire in 24 hours.</p>'
            '</div>'
        )

        # Send email
        email_message = EmailMultiAlternatives(
            subject, message_text, 'info@nilltechsolutions.com', [user.email])
        email_message.attach_alternative(message_html, "text/html")
        email_message.send()

        return Response({"message": "Verification email resent."}, status=status.HTTP_200_OK)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="JWT tokens and user type returned."),
            400: OpenApiResponse(description="Invalid credentials.")
        },
        description="Authenticate user and return JWT tokens."
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_type": getattr(user.profile, 'user_type', 'N/A')
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid or expired refresh token.")
        },
        description="Invalidate JWT refresh token."
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if serializer.is_valid():
            refresh_token = serializer.validated_data['refresh']
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response({"message": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
            except TokenError:
                return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Password updated."),
            400: OpenApiResponse(description="Invalid input.")
        },
        description="Change user password."
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            request.user.set_password(
                serializer.validated_data['new_password1'])
            request.user.save()
            return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description="Password reset email sent."),
            400: OpenApiResponse(description="Invalid email.")
        },
        description="Request password reset email."
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(
                    email=serializer.validated_data['email'])
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                current_site = get_current_site(request)
                reset_url = f'http://{current_site.domain}/api/v1/accounts/password-reset-confirm/{uid}/{token}/'

                subject = 'Reset Your Password'
                message_text = f'Hi {user.username},\n\nPlease click the link to reset your password: {reset_url}'
                message_html = format_html(
                    '<div style="font-family: Arial, sans-serif; text-align: center;">'
                    f'<h2>Hi {user.username},</h2>'
                    '<p>Please click the button below to reset your password:</p>'
                    f'<a href="{reset_url}" style="display: inline-block; background-color: #dc3545; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-size: 16px;">'
                    'Reset Password</a><p>If you didn\'t request this, ignore this email.</p>'
                    '</div>'
                )
                email = EmailMultiAlternatives(
                    subject, message_text, 'info@nilltechsolutions.com', [user.email])
                email.attach_alternative(message_html, "text/html")
                email.send()

                return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"message": "Email sent."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successful."),
            400: OpenApiResponse(description="Invalid token.")
        },
        description="Confirm password reset."
    )
    def post(self, request, uidb64, token):
        serializer = PasswordResetConfirmSerializer(
            data={'uidb64': uidb64, 'token': token, 'new_password': request.data.get('new_password')})
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
                if default_token_generator.check_token(user, token):
                    user.set_password(
                        serializer.validated_data['new_password'])
                    user.save()
                    return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)
                return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
            except (TypeError, ValueError, User.DoesNotExist):
                return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    @extend_schema(
        description="List profiles (admin only) or retrieve specific profile.",
        responses={200: ProfileSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve user profile.",
        responses={200: ProfileSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=ProfileSerializer,
        description="Update user profile (owner or admin only).",
        responses={200: ProfileSerializer,
                   400: OpenApiResponse(description="Invalid input.")}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete user profile (owner or admin only).",
        responses={204: OpenApiResponse(description="Profile deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(
        description="List or create skills (admin only).",
        responses={200: SkillSerializer(many=True), 201: SkillSerializer}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=SkillSerializer,
        description="Create a new skill (admin only).",
        responses={201: SkillSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve skill details.",
        responses={200: SkillSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=SkillSerializer,
        description="Update skill (admin only).",
        responses={200: SkillSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete skill (admin only).",
        responses={204: OpenApiResponse(description="Skill deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(
        description="List or create languages (admin only).",
        responses={200: LanguageSerializer(many=True), 201: LanguageSerializer}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=LanguageSerializer,
        description="Create a new language (admin only).",
        responses={201: LanguageSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve language details.",
        responses={200: LanguageSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=LanguageSerializer,
        description="Update language (admin only).",
        responses={200: LanguageSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete language (admin only).",
        responses={204: OpenApiResponse(description="Language deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListFreelancersView(generics.ListAPIView):
    queryset = FreelancerProfile.objects.select_related(
        'profile__user').prefetch_related('languages', 'skills')
    serializer_class = FreelancerListSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 🔍 Enable search, filtering, and ordering
    filter_backends = [filters.SearchFilter,
                       filters.OrderingFilter, DjangoFilterBackend]

    search_fields = [
        'profile__user__email',
        'profile__location',
        'languages__name',
        'skills__name',
    ]

    ordering_fields = [
        'profile__user__email',  # indirect, optional if you want to allow sorting by email
    ]

    filterset_fields = [
        'languages__name',
        'skills__name',
        'profile__location',
    ]


class ClientListView(generics.ListAPIView):
    queryset = ClientProfile.objects.select_related(
        'profile__user').prefetch_related('languages')
    serializer_class = ClientListSerializer
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [filters.SearchFilter,
                       filters.OrderingFilter, DjangoFilterBackend]

    search_fields = [
        'company_name',
        'industry',
        'profile__location',
        'languages__name',
        'profile__user__email',
    ]

    ordering_fields = [
        'project_budget',
        'company_name',
    ]

    filterset_fields = [
        'industry',
        'languages__name',
        'preferred_freelancer_level',
        'project_budget',
    ]


class FreelancerFormView(APIView):
    permission_classes = [permissions.IsAuthenticated,
                          IsFreelancerOrAdminOrClientReadOnly]

    def get_object(self, user):
        try:
            return user.profile.freelancer_profile
        except (Profile.DoesNotExist, FreelancerProfile.DoesNotExist):
            return None

    @extend_schema(
        responses={200: FreelancerFormSerializer},
        description="Retrieve freelancer profile by user ID or email."
    )
    def get(self, request):
        user_id = request.query_params.get('id')
        email = request.query_params.get('email')

        # Determine which user's profile to fetch
        if user_id:
            target_user = User.objects.filter(id=user_id).first()
        elif email:
            target_user = User.objects.filter(email=email).first()
        else:
            target_user = request.user  # fallback to self

        if not target_user:
            return Response({"error": "User not found."}, status=404)

        try:
            freelancer_profile = target_user.profile.freelancer_profile
        except (Profile.DoesNotExist, FreelancerProfile.DoesNotExist):
            return Response({"error": "Freelancer profile not found."}, status=404)

        serializer = FreelancerFormSerializer(freelancer_profile)
        return Response(serializer.data)

    @extend_schema(
        request=FreelancerFormSerializer,
        responses={200: OpenApiResponse(
            description="Freelancer profile created/updated")},
        description="Create or update freelancer profile."
    )
    def post(self, request):
        user = request.user
        freelancer_profile = self.get_object(user)

        if freelancer_profile:
            serializer = FreelancerFormSerializer(
                freelancer_profile, data=request.data, context={'request': request})
        else:
            serializer = FreelancerFormSerializer(
                data=request.data, context={'request': request})

        if serializer.is_valid():
            instance = serializer.save()
            if 'languages' in serializer.validated_data:
                instance.languages.set(serializer.validated_data['languages'])
            if 'skills' in serializer.validated_data:
                instance.skills.set(serializer.validated_data['skills'])

            return Response({"message": "Freelancer profile created/updated"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: OpenApiResponse(
            description="Freelancer profile deleted")},
        description="Delete freelancer profile."
    )
    def delete(self, request):
        freelancer_profile = self.get_object(request.user)
        if not freelancer_profile:
            return Response({"error": "Freelancer profile not found"}, status=404)

        freelancer_profile.delete()
        return Response({"message": "Freelancer profile deleted"}, status=status.HTTP_204_NO_CONTENT)


class ClientFormView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, user):
        try:
            return user.profile.client_profile
        except (Profile.DoesNotExist, ClientProfile.DoesNotExist):
            return None

    @extend_schema(
        responses={200: ClientFormSerializer},
        description="Retrieve client profile by user ID or email."
    )
    def get(self, request):
        user_id = request.query_params.get('id')
        email = request.query_params.get('email')

        if user_id:
            user = User.objects.filter(id=user_id).first()
        elif email:
            user = User.objects.filter(email=email).first()
        else:
            user = request.user

        if not user:
            return Response({"error": "User not found."}, status=404)

        client_profile = self.get_object(user)
        if not client_profile:
            return Response({"error": "Client profile not found."}, status=404)

        serializer = ClientFormSerializer(client_profile)
        return Response(serializer.data)

    @extend_schema(
        request=ClientFormSerializer,
        responses={200: OpenApiResponse(
            description="Client profile created/updated")},
        description="Create or update client profile."
    )
    def post(self, request):
        client_profile = self.get_object(request.user)

        if client_profile:
            serializer = ClientFormSerializer(
                client_profile, data=request.data, context={'request': request})
        else:
            serializer = ClientFormSerializer(
                data=request.data, context={'request': request})

        if serializer.is_valid():
            instance = serializer.save()
            if 'languages' in serializer.validated_data:
                instance.languages.set(serializer.validated_data['languages'])
            return Response({"message": "Client profile created/updated"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={204: OpenApiResponse(description="Client profile deleted")},
        description="Delete client profile."
    )
    def delete(self, request):
        client_profile = self.get_object(request.user)
        if not client_profile:
            return Response({"error": "Client profile not found"}, status=404)

        client_profile.delete()
        return Response({"message": "Client profile deleted"}, status=status.HTTP_204_NO_CONTENT)
