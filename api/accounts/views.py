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
from rest_framework.permissions import AllowAny,IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter


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
from django.conf import settings
from urllib.parse import urlencode

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
        summary="List all users (admin only)",
        responses={
            200: UserSerializer(many=True),
            403: OpenApiResponse(description="Admin access required.")
        }
    )
    def list(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve a user",
        responses={200: UserSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update a user",
        request=UserSerializer,
        responses={200: UserSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a user",
        responses={204: OpenApiResponse(
            description="User deleted successfully.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        summary="Register a new user",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User created, verification email sent."),
            400: OpenApiResponse(description="Validation error")
        }
    )

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            def build_verify_email_url(uid, token):
                base_url = settings.FRONTEND_URL.rstrip("/")
                query_params = urlencode({"uid": uid, "token": token})
                return f"{base_url}/auth/verify-email/?{query_params}"

            current_site = build_verify_email_url(uid, token)
            verification_url = f'{current_site}'

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

            return Response({"message": "User created, verification email sent. Please check you eamil inbox or spam"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Verify Email",
        description="Verify user email using the token from the email link. Returns JWT tokens on success.",
        responses={
            200: OpenApiResponse(description="Email verified, JWT tokens returned."),
            400: OpenApiResponse(description="Invalid or expired token.")
        }
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
        summary="Resend verification email",
        description="Resend the email verification link. Requires the email field.",
        request=ResendVerificationSerializer,
        responses={
            200: OpenApiResponse(description="Verification email resent."),
            400: OpenApiResponse(description="User not found or already verified.")
        }
    )
    def post(self, request):
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
        
        def build_verify_email_url(uid, token):
                    base_url = settings.FRONTEND_URL.rstrip("/")
                    query_params = urlencode({"uid": uid, "token": token})
                    return f"{base_url}/auth/verify-email/?{query_params}"
        
        
        current_site = build_verify_email_url(uid,token)
        verification_url = f'{current_site}'

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
            subject, message_text, 'info@nilltechsolutions.com', [user.email]
        )
        email_message.attach_alternative(message_html, "text/html")
        email_message.send()

        return Response({"message": "Verification email resent."}, status=status.HTTP_200_OK)



class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="User Login",
        description="Authenticate user and return JWT tokens. Use `remember_me=true` for 30-day session.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Login successful. JWT tokens and user info returned."),
            400: OpenApiResponse(description="Invalid credentials.")
        }
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
            
            # Get user_type from related profile
            user_type = getattr(user.profile, 'user_type', None)
            email_verified = getattr(user, 'is_active',None)

            # Create response
            res = Response({
                "message": "Login successful.",
                "user": AuthUserSerializer(user).data,
                "user_type":user_type,
                "email_verified":email_verified,
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
        summary="User Logout",
        description="Blacklist the refresh token to log out the user.",
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid or expired refresh token.")
        }
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
        summary="Change Password",
        description="Authenticated user can change their password.",
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Password updated."),
            400: OpenApiResponse(description="Invalid input.")
        }
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
        summary="Request Password Reset",
        description="Sends a password reset email if the email is registered.",
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description="Password reset email sent."),
            400: OpenApiResponse(description="Invalid email.")
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(
                    email=serializer.validated_data['email'])
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                def build_password_reset_url(uid, token):
                    base_url = settings.FRONTEND_URL.rstrip("/")
                    query_params = urlencode({"uid": uid, "token": token})
                    return f"{base_url}/auth/password-reset-confirm/?{query_params}"
                
                current_site = build_password_reset_url(uid,token)
                reset_url = f'{current_site}'

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
        summary="Confirm Password Reset",
        description="Reset password using token and UID from email link.",
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successful."),
            400: OpenApiResponse(description="Invalid or expired token.")
        }
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


@extend_schema(
    summary="Get or update your own profile",
    description="GET returns current user's profile. PUT/PATCH updates it. DELETE deletes the profile.",
    request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "profile_pic": {
                        "type": "string",
                        "format": "binary",
                        "description": "Optional profile picture file"
                    },
                    "phone": {"type": "string"},
                    "location": {"type": "string"},
                    "bio": {"type": "string"},
                    "pay_id": {"type": "string"},
                    "pay_id_no": {"type": "string"},
                    "id_card": {
                        "type": "string",
                        "format": "binary",
                        "description": "National ID or document"
                    },
                },
                "required": []
            }
    },
    responses={
        200: ProfileSerializer,
        204: OpenApiResponse(description="Profile deleted successfully."),
        400: OpenApiResponse(description="Validation error.")
    },
    methods=["GET", "PUT", "PATCH", "DELETE"]
)
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
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(summary="List skills", responses=SkillSerializer(many=True))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a skill", request=SkillSerializer, responses=SkillSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Retrieve a skill", responses=SkillSerializer)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a skill", request=SkillSerializer, responses=SkillSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Delete a skill", responses={204: OpenApiResponse(description="Deleted")})
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LanguageViewSet(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(summary="List languages", responses=LanguageSerializer(many=True))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create a language", request=LanguageSerializer, responses=LanguageSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Retrieve a language", responses=LanguageSerializer)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update a language", request=LanguageSerializer, responses=LanguageSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Delete a language", responses={204: OpenApiResponse(description="Deleted")})
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="List available freelancers",
    description="Returns a filtered and searchable list of visible freelancer profiles.",
    responses={200: FreelancerListSerializer(many=True)},
)
class ListFreelancersView(generics.ListAPIView):
    queryset = FreelancerProfile.objects.select_related('profile__user').prefetch_related('languages', 'skills')
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


@extend_schema(
    summary="List client profiles",
    description="Search and filter client profiles based on company, industry, budget, and other criteria.",
    responses={200: ClientListSerializer(many=True)},
)
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


@extend_schema(
    summary="Create, update, retrieve or delete client profile",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string"},
                        "location": {"type": "string"},
                        "bio": {"type": "string"},
                        "pay_id": {"type": "string"},
                        "pay_id_no": {"type": "string"},
                        "profile_pic": {
                            "type": "string",
                            "format": "binary",
                            "description": "Profile picture"
                        },
                        "id_card": {
                            "type": "string",
                            "format": "binary",
                            "description": "National ID or verification doc"
                        }
                    }
                },
                "company_name": {"type": "string"},
                "company_website": {"type": "string"},
                "industry": {"type": "string"},
                "project_budget": {"type": "number"},
                "preferred_freelancer_level": {"type": "string"},
                "languages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of language IDs"
                },
                "is_verified": {"type": "boolean"}
            }
        }
    },
    responses={
        201: OpenApiResponse(description="Client profile created successfully."),
        200: OpenApiResponse(description="Client profile updated successfully."),
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Permission denied."),
        204: OpenApiResponse(description="Client profile deleted.")
    }
)

class ClientWriteViewSet(viewsets.ModelViewSet):
    serializer_class = ClientProfileWriteSerializer
    permission_classes = [permissions.IsAuthenticated,IsOwnerOrReadOnly]
    lookup_field = 'slug'

    def get_queryset(self):
        return ClientProfile.objects.filter(profile__user=self.request.user)

    def get_object(self):
        request = self.request
        identifier = (
            self.kwargs.get('client_profile_slug')
            or self.kwargs.get('slug')
            or self.kwargs.get('user_id')
            or self.kwargs.get('username')
        )

        logger.debug(f"Fetching object with identifier: {identifier}")

        if identifier == 'me':
            obj = get_object_or_404(ClientProfile, profile__user=request.user)
        else:
            try:
                obj = ClientProfile.objects.get(slug=identifier)
            except ClientProfile.DoesNotExist:
                try:
                    user = User.objects.get(id=identifier)
                    obj = ClientProfile.objects.get(profile__user=user)
                except (User.DoesNotExist, ClientProfile.DoesNotExist):
                    try:
                        user = User.objects.get(username=identifier)
                        obj = ClientProfile.objects.get(profile__user=user)
                    except (User.DoesNotExist, ClientProfile.DoesNotExist):
                        logger.warning(
                            f"No client profile found for identifier: {identifier}")
                        raise Http404("Client profile not found.")

        if obj.profile.user != request.user:
            logger.warning(
                f"Permission denied for user {request.user} on profile {obj.slug}")
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
        

@extend_schema(
    summary="Retrieve public freelancer profile",
    description="Get a visible freelancer profile by username or 'me' if authenticated.",
    responses={200: FreelancerProfileReadSerializer}
)
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
        

@extend_schema(
    summary="Create, update, retrieve or delete freelancer profile",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string"},
                        "location": {"type": "string"},
                        "bio": {"type": "string"},
                        "pay_id": {"type": "string"},
                        "pay_id_no": {"type": "string"},
                        "profile_pic": {
                            "type": "string",
                            "format": "binary",
                            "description": "Profile picture"
                        },
                        "id_card": {
                            "type": "string",
                            "format": "binary",
                            "description": "National ID or verification doc"
                        }
                    }
                },
                "experience_years": {"type": "integer"},
                "hourly_rate": {"type": "number"},
                "availability": {"type": "string"},
                "languages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of language IDs"
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of skill IDs"
                },
                "is_visible": {"type": "boolean"}
            }
        }
    },
    responses={
        201: OpenApiResponse(description="Freelancer profile created successfully."),
        200: OpenApiResponse(description="Freelancer profile updated successfully."),
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Permission denied."),
        204: OpenApiResponse(description="Freelancer profile deleted.")
    }
)
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
        
