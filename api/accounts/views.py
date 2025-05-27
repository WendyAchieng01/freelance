from rest_framework.views import APIView
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

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
from ..permissions import IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, CanReview

from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    PasswordChangeSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, ProfileSerializer, SkillSerializer,
    LanguageSerializer, FreelancerProfileSerializer, ClientProfileSerializer,
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
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Verification email resent."),
            400: OpenApiResponse(description="User not found or already verified.")
        },
        description="Resend verification email."
    )
    def post(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id, is_active=False)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            current_site = get_current_site(request)
            verification_url = f'http://{current_site.domain}/api/v1/accounts/verify-email/{uid}/{token}/'

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
            email = EmailMultiAlternatives(
                subject, message_text, 'info@nilltechsolutions.com', [user.email])
            email.attach_alternative(message_html, "text/html")
            email.send()

            return Response({"message": "Verification email resent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found or already verified."}, status=status.HTTP_400_BAD_REQUEST)


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
                "user_type": user.profile.user_type
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={'refresh': 'string'},
        responses={
            205: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid refresh token.")
        },
        description="Invalidate JWT refresh token."
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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


class FreelancerProfileViewSet(viewsets.ModelViewSet):
    queryset = FreelancerProfile.objects.all()
    serializer_class = FreelancerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(profile__user=self.request.user)

    @extend_schema(
        description="List freelancer profiles (admin or owner only).",
        responses={200: FreelancerProfileSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve freelancer profile.",
        responses={200: FreelancerProfileSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['username'] = instance.profile.user.username
        data['has_rated'] = CoreResponse.objects.filter(
            reviewer=request.user, recipient=instance.profile.user
        ).exists() if request.user != instance.profile.user else False
        return Response(data)

    @extend_schema(
        request=FreelancerProfileSerializer,
        description="Create or update freelancer profile (owner or admin only).",
        responses={200: FreelancerProfileSerializer,
                   201: FreelancerProfileSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=FreelancerProfileSerializer,
        description="Update freelancer profile (owner or admin only).",
        responses={200: FreelancerProfileSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete freelancer profile (owner or admin only).",
        responses={204: OpenApiResponse(
            description="Freelancer profile deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientProfileViewSet(viewsets.ModelViewSet):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(profile__user=self.request.user)

    @extend_schema(
        description="List client profiles (admin or owner only).",
        responses={200: ClientProfileSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Retrieve client profile.",
        responses={200: ClientProfileSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        data['username'] = instance.profile.user.username
        data['has_rated'] = CoreResponse.objects.filter(
            reviewer=request.user, recipient=instance.profile.user
        ).exists() if request.user != instance.profile.user else False
        return Response(data)

    @extend_schema(
        request=ClientProfileSerializer,
        description="Create or update client profile (owner or admin only).",
        responses={200: ClientProfileSerializer, 201: ClientProfileSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=ClientProfileSerializer,
        description="Update client profile (owner or admin only).",
        responses={200: ClientProfileSerializer}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        description="Delete client profile (owner or admin only).",
        responses={204: OpenApiResponse(description="Client profile deleted.")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FreelancerFormView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: FreelancerFormSerializer},
        description="Retrieve freelancer profile form data."
    )
    def get(self, request):
        profile = request.user.profile
        try:
            freelancer_profile = profile.freelancer_profile
            data = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
                'phone_number': profile.phone,
                'experience_years': freelancer_profile.experience_years,
                'hourly_rate': freelancer_profile.hourly_rate,
                'languages': freelancer_profile.languages.all(),
                'photo': profile.profile_pic,
                'id_number': profile.id_card,
                'location': profile.location,
                'pay_id': profile.pay_id,
                'pay_id_no': profile.pay_id_no,
                'skills': freelancer_profile.skills.all(),
                'portfolio_link': freelancer_profile.portfolio_link,
                'availability': freelancer_profile.availability
            }
            serializer = FreelancerFormSerializer(data)
            return Response(serializer.data)
        except FreelancerProfile.DoesNotExist:
            return Response(FreelancerFormSerializer().data)

    @extend_schema(
        request=FreelancerFormSerializer,
        responses={
            200: OpenApiResponse(description="Freelancer profile updated."),
            400: OpenApiResponse(description="Invalid input.")
        },
        description="Create or update freelancer profile."
    )
    def post(self, request):
        serializer = FreelancerFormSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "Freelancer profile updated."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientFormView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: ClientFormSerializer},
        description="Retrieve client profile form data."
    )
    def get(self, request):
        profile = request.user.profile
        try:
            client_profile = profile.client_profile
            data = {
                'company_name': client_profile.company_name or request.user.username,
                'email': request.user.email,
                'phone_number': profile.phone,
                'industry': client_profile.industry,
                'languages': client_profile.languages.all(),
                'location': profile.location,
                'pay_id': profile.pay_id,
                'pay_id_no': profile.pay_id_no,
                'company_website': client_profile.company_website,
                'project_budget': client_profile.project_budget,
                'preferred_freelancer_level': client_profile.preferred_freelancer_level
            }
            serializer = ClientFormSerializer(data)
            return Response(serializer.data)
        except ClientProfile.DoesNotExist:
            return Response(ClientFormSerializer().data)

    @extend_schema(
        request=ClientFormSerializer,
        responses={
            200: OpenApiResponse(description="Client profile updated."),
            400: OpenApiResponse(description="Invalid input.")
        },
        description="Create or update client profile."
    )
    def post(self, request):
        serializer = ClientFormSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "Client profile updated."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
