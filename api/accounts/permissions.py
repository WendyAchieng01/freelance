from rest_framework import permissions
from accounts.models import Profile
from core.models import Job, Chat, Response, Review
from django.contrib.auth import get_user_model

User = get_user_model()


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.profile.user == request.user

class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'client'


class IsFreelancer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'freelancer'
    
    
class IsFreelancerOrAdminOrClientReadOnly(permissions.BasePermission):
    """
    - Admins can do everything
    - Freelancers can create, read, update, delete their own profile
    - Clients can only read
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        user_type = getattr(getattr(user, 'profile', None), 'user_type', None)

        if request.method in permissions.SAFE_METHODS:
            return True  # All authenticated users can read

        # Only allow full permissions to admin or freelancer
        return user.is_staff or user_type == 'freelancer'

    def has_object_permission(self, request, view, obj):
        user = request.user
        user_type = getattr(getattr(user, 'profile', None), 'user_type', None)

        if request.method in permissions.SAFE_METHODS:
            return True

        # Only admin or the freelancer who owns the profile
        return user.is_staff or (user_type == 'freelancer' and obj.profile.user == user)


class IsClientOrAdminFreelancerReadOnly(permissions.BasePermission):
    """
    - Admins and clients have full access
    - Freelancers can only read
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        user_type = getattr(getattr(user, 'profile', None), 'user_type', None)

        # SAFE methods (GET, HEAD, OPTIONS): All authenticated users can read
        if request.method in permissions.SAFE_METHODS:
            return True

        # Only client or admin can write
        return user.is_staff or user_type == 'client'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        user_type = getattr(getattr(user, 'profile', None), 'user_type', None)

        return user.is_staff or user_type == 'client'



class IsJobOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        return hasattr(obj, 'client') and obj.client.user == request.user


class IsChatParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.profile in [obj.client, obj.freelancer]


class CanReview(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ['POST', 'PUT', 'PATCH']:
            recipient_id = request.data.get('recipient')
            if not recipient_id:
                return False
            try:
                recipient = User.objects.get(id=recipient_id)
                if request.user.profile.user_type == 'client':
                    return Job.objects.filter(client=request.user.profile, selected_freelancer=recipient, status='completed').exists()
                else:
                    return Job.objects.filter(client=recipient.profile, selected_freelancer=request.user, status='completed').exists()
            except User.DoesNotExist:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        return obj.reviewer == request.user
