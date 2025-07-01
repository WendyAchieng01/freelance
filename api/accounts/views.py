from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta, datetime
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.decorators import action
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework import viewsets, status, permissions,generics,filters,mixins
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken,TokenError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.parsers import JSONParser
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.permissions import AllowAny,IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.settings import api_settings as jwt_settings


from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.utils.html import format_html
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.http import FileResponse, Http404
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.shortcuts import get_object_or_404

from accounts.models import Profile, FreelancerProfile, ClientProfile, Skill, Language
from api.accounts.filters import FreelancerProfileFilter,ClientProfileFilter
from core.models import Job, Response as CoreResponse, Chat, Message, MessageAttachment, Review
from .permissions import IsOwnerOrAdmin,IsClient, IsFreelancer, IsJobOwner,CanReview,IsFreelancerOrAdminOrClientReadOnly,IsClientOrAdminFreelancerReadOnly,IsOwnerOrReadOnly

from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,LogoutSerializer,AuthUserSerializer,
    PasswordChangeSerializer, PasswordResetRequestSerializer,ResendVerificationSerializer,
    PasswordResetConfirmSerializer, ProfileSerializer, SkillSerializer,FreelancerProfileReadSerializer,
    LanguageSerializer,FreelancerListSerializer,FreelancerProfileWriteSerializer,
    ClientProfileWriteSerializer, ClientProfileReadSerializer,ClientListSerializer
)

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

User = get_user_model()





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
            verification_url = f'http://{current_site.domain}/api/v1/verify-email/{uid}/{token}/'

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
        verification_url = f'http://{current_site.domain}/api/v1/verify-email/{uid}/{token}/'

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
        responses={200: OpenApiResponse(
            description="JWT tokens and user info returned")},
        description="Authenticate user and return tokens. Set remember_me=true for long-lived cookies."
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            remember_me = serializer.validated_data.get('remember_me', False)

            refresh = RefreshToken.for_user(user)

            # Token lifetimes
            if remember_me:
                refresh.set_exp(lifetime=timedelta(days=30))
                access_lifetime = timedelta(days=7)
            else:
                access_lifetime = timedelta(minutes=5)  # default

            refresh.access_token.set_exp(lifetime=access_lifetime)

            access_token = refresh.access_token

            # Create response
            res = Response({
                "message": "Login successful.",
                "user": AuthUserSerializer(user).data,
                "access": str(access_token),
                "refresh": str(refresh),
                "access_expires": datetime.fromtimestamp(access_token['exp']).isoformat(),
                "refresh_expires": datetime.fromtimestamp(refresh['exp']).isoformat()
            }, status=status.HTTP_200_OK)

            # Set cookies 
            res.set_cookie(
                key="access_token",
                value=str(access_token),
                expires=access_token['exp'],
                httponly=True,
                secure=True,
                samesite='Lax'
            )
            res.set_cookie(
                key="refresh_token",
                value=str(refresh),
                expires=refresh['exp'],
                httponly=True,
                secure=True,
                samesite='Lax'
            )

            return res

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
                reset_url = f'http://{current_site.domain}/api/v1/password-reset-confirm/{uid}/{token}/'

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


class ProfileViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Show only opposite user_type profiles (exclude own)
        opposite_type = 'client' if user.profile.user_type == 'freelancer' else 'freelancer'
        return Profile.objects.filter(user_type=opposite_type).exclude(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        if Profile.objects.filter(user=user).exists():
            raise ValidationError("This user already has a profile.")
        serializer.save(user=user)

    @action(detail=False, methods=['get', 'put', 'patch', 'delete'], url_path='me')
    def me(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            user = AuthUserSerializer(request.user)
            return Response(serializer.data)
        
        elif request.method in ['PUT', 'PATCH']:
            serializer = self.get_serializer(
                profile, data=request.data, partial=(request.method == 'PATCH'))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        elif request.method == 'DELETE':
            profile.delete()
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

    #  Enable search, filtering, and ordering
    filter_backends = [filters.SearchFilter,filters.OrderingFilter, DjangoFilterBackend]
    
    filterset_class = FreelancerProfileFilter

    search_fields = [
        'profile__user__email',
        'profile__location',
        'languages__name',
        'skills__name',
    ]

    ordering_fields = [
        'profile__user__email', 'experience_years', 'profile__location','hourly_rate'
    ]

    filterset_fields = [
        'languages__name',
        'skills__name',
        'profile__location',
        'experience_years', 
        'hourly_rate',                   
        'availability',
        'profile__user__first_name',    
        'profile__user__last_name',
        'is_visible',                   
    ]


class ClientProfileListView(generics.ListAPIView):
    queryset = ClientProfile.objects.select_related(
        'profile__user').prefetch_related('languages')
    serializer_class = ClientListSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'industry': ['exact', 'in'],
        'languages__name': ['exact', 'in'],
        'preferred_freelancer_level': ['exact', 'in'],
        'project_budget': ['exact', 'gte', 'lte'],
        'is_verified': ['exact'],
        'profile__location': ['exact', 'icontains'],
        'profile__user__email': ['exact', 'icontains'],
    }
    filterset_class = ClientProfileFilter
    search_fields = ['company_name',
                        'profile__user__first_name', 'profile__user__last_name']
    ordering_fields = ['company_name', 'project_budget']


class ClientWriteViewSet(viewsets.ModelViewSet):
    serializer_class = ClientProfileWriteSerializer
    permission_classes = [permissions.IsAuthenticated,IsOwnerOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        return ClientProfile.objects.filter(profile__user=self.request.user)

    def get_object(self):
        identifier = self.kwargs.get(
            'client_profile_slug') or self.kwargs.get('slug')
        logger.debug(f"Fetching object with identifier: {identifier}")
        if identifier == 'me':
            obj = get_object_or_404(
                ClientProfile, profile__user=self.request.user)
        else:
            obj = get_object_or_404(ClientProfile, slug=identifier)
        if obj.profile.user != self.request.user:
            logger.warning(
                f"Permission denied for user {self.request.user} on profile {obj.slug}")
            raise PermissionDenied(
                "You do not have permission to access this profile.")
        return obj

    def create(self, request, *args, **kwargs):
        logger.debug(
            f"Creating client profile for user: {request.user.username}")
        if ClientProfile.objects.filter(profile__user=request.user).exists():
            logger.warning(
                f"Profile already exists for user: {request.user.username}")
            return Response({
                "message": "Client profile already exists.",
                "data": None,
                "http_code": status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        read_serializer = ClientProfileReadSerializer(client)
        logger.info(
            f"Client profile created for user: {request.user.username}")
        return Response({
            "message": "Client profile created successfully.",
            "data": read_serializer.data,
            "http_code": status.HTTP_201_CREATED
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ClientProfileReadSerializer(instance)
        logger.debug(f"Retrieved profile: {instance.slug}")
        return Response({
            "message": "Client profile retrieved successfully.",
            "data": serializer.data,
            "http_code": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, context={'request': request}, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        read_serializer = ClientProfileReadSerializer(client)
        logger.info(f"Updated profile: {client.slug}")
        return Response({
            "message": "Client profile updated successfully.",
            "data": read_serializer.data,
            "http_code": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        logger.info(f"Deleted profile: {instance.slug}")
        return Response({
            "message": "Client profile deleted successfully.",
            "data": None,
            "http_code": status.HTTP_204_NO_CONTENT
        }, status=status.HTTP_204_NO_CONTENT)
        

class FreelancerReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FreelancerProfileReadSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'username'

    def get_queryset(self):
        return FreelancerProfile.objects.filter(is_visible=True)

    def get_object(self):
        identifier = self.kwargs.get('username')

        if identifier == 'me':
            if not self.request.user.is_authenticated:
                raise PermissionDenied(
                    "Authentication required to access your profile.")
            return get_object_or_404(FreelancerProfile, profile__user=self.request.user)

        user = get_object_or_404(User, username=identifier)
        return get_object_or_404(FreelancerProfile, profile__user=user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Freelancer profile retrieved successfully.",
            "data": serializer.data,
            "http_code": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)
        
        
class FreelancerWriteViewSet(viewsets.ModelViewSet):
    serializer_class = FreelancerProfileWriteSerializer
    permission_classes = [permissions.IsAuthenticated,IsOwnerOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        return FreelancerProfile.objects.filter(profile__user=self.request.user)

    def get_object(self):
        identifier = self.kwargs.get(
            'freelance_profile_slug') or self.kwargs.get('slug')
        logger.debug(f"Fetching object with identifier: {identifier}")
        if identifier == 'me':
            obj = get_object_or_404(
                FreelancerProfile, profile__user=self.request.user)
        else:
            obj = get_object_or_404(FreelancerProfile, slug=identifier)
        if obj.profile.user != self.request.user:
            logger.warning(
                f"Permission denied for user {self.request.user} on profile {obj.slug}")
            raise PermissionDenied(
                "You do not have permission to access this profile.")
        return obj

    def create(self, request, *args, **kwargs):
        logger.debug(
            f"Creating freelancer profile for user: {request.user.username}")
        if FreelancerProfile.objects.filter(profile__user=request.user).exists():
            logger.warning(
                f"Profile already exists for user: {request.user.username}")
            return Response({
                "message": "Freelancer profile already exists.",
                "data": None,
                "http_code": status.HTTP_400_BAD_REQUEST
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        freelancer = serializer.save()
        read_serializer = FreelancerProfileReadSerializer(freelancer)
        logger.info(
            f"Freelancer profile created for user: {request.user.username}")
        return Response({
            "message": "Freelancer profile created successfully.",
            "data": read_serializer.data,
            "http_code": status.HTTP_201_CREATED
        }, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = FreelancerProfileReadSerializer(instance)
        logger.debug(f"Retrieved profile: {instance.slug}")
        return Response({
            "message": "Freelancer profile retrieved successfully.",
            "data": serializer.data,
            "http_code": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, context={'request': request}, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        freelancer = serializer.save()
        read_serializer = FreelancerProfileReadSerializer(freelancer)
        logger.info(f"Updated profile: {freelancer.slug}")
        return Response({
            "message": "Freelancer profile updated successfully.",
            "data": read_serializer.data,
            "http_code": status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        logger.info(f"Deleted profile: {instance.slug}")
        return Response({
            "message": "Freelancer profile deleted successfully.",
            "data": None,
            "http_code": status.HTTP_204_NO_CONTENT
        }, status=status.HTTP_204_NO_CONTENT)
        
