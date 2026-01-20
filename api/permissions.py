from rest_framework import permissions
from accounts.models import Profile
from core.models import Job, Chat, Response, Review
from django.contrib.auth import get_user_model

User = get_user_model()


class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'client'


class IsFreelancer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'freelancer'


class IsJobOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return hasattr(obj, 'client') and obj.client.user == request.user


class CanReview(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in ['POST', 'PUT', 'PATCH']:
            recipient_id = request.data.get('recipient')
            if not recipient_id:
                return False
            try:
                recipient = User.objects.get(id=recipient_id)
                if request.user.profile.user_type == 'client':
                    return Job.objects.filter(client=request.user.profile, selected_freelancers=recipient, status='completed').exists()
                else:
                    return Job.objects.filter(client=recipient.profile, selected_freelancers=request.user, status='completed').exists()
            except User.DoesNotExist:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        return obj.reviewer == request.user
