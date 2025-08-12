from rest_framework.exceptions import PermissionDenied
from accounts.models import Profile
from rest_framework.permissions import BasePermission
from rest_framework import permissions
from accounts.models import Profile
from core.models import Job, Chat, Response, Review
from django.contrib.auth import get_user_model
from django.db.models import Q


User = get_user_model()


class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'client'


class IsFreelancer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_type == 'freelancer'


class IsJobOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        # Only enforce object-level check for update/delete actions
        return view.action in ['update', 'partial_update', 'destroy']

    def has_object_permission(self, request, view, obj):
        return hasattr(obj, 'client') and obj.client.user == request.user


class IsResponseOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsJobOwnerCanEditEvenIfAssigned(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.client.user == request.user

class IsClientOfJob(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.job.client.user == request.user


class IsChatParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.profile in [obj.client, obj.freelancer]

    def has_permission(self, request, view):
        return request.user.is_authenticated


class CanReview(permissions.BasePermission):
    """
    Permission to allow reviews only between:
    - The job owner (client) and the selected freelancer
    - The job must be marked as completed
    """

    message = "You do not have permission to review this user."

    def has_permission(self, request, view):
        if request.method in ['POST', 'PUT', 'PATCH']:
            recipient_id = request.data.get('recipient')
            if not recipient_id:
                self.message = "Recipient ID is required to submit a review."
                return False

            try:
                recipient = User.objects.get(id=recipient_id)
            except User.DoesNotExist:
                self.message = "The specified recipient does not exist."
                return False

            if request.user.profile.user_type == 'client':
                job = Job.objects.filter(
                    client=request.user.profile,
                    selected_freelancer=recipient,
                    status='completed'
                ).first()
                if not job:
                    self.message = (
                        "You can only review a freelancer if they were selected "
                        "for your job and the job is marked as completed."
                    )
                    return False
                return True

            elif request.user.profile.user_type == 'freelancer':
                job = Job.objects.filter(
                    client=recipient.profile,
                    selected_freelancer=request.user,
                    status='completed'
                ).first()
                if not job:
                    self.message = (
                        "You can only review a client if they owned a job you "
                        "completed as the selected freelancer."
                    )
                    return False
                return True

            self.message = "Invalid user type for leaving a review."
            return False

        return True

    def has_object_permission(self, request, view, obj):
        if obj.reviewer != request.user:
            self.message = "You can only edit or delete your own reviews."
            return False
        return True
    
    
class IsChatParticipant(permissions.BasePermission):
    """
    Allow access only if:
    - The requesting user is the job's client, OR
    - The requesting user is the job's selected freelancer
    AND
    - The job's payment is verified
    """

    message = "You do not have permission to access this chat."

    def has_object_permission(self, request, view, obj):
        # If obj is a Message, get its Chat
        chat = obj.chat if hasattr(obj, 'chat') else obj
        job = chat.job

        # Payment must be verified
        if not job.payment_verified:
            self.message = "Access denied: Job payment has not been verified."
            return False

        # If user is the job's client
        if chat.client.user == request.user:
            return True

        # If user is the selected freelancer
        if job.selected_freelancer and chat.freelancer and chat.freelancer.user == request.user:
            if job.selected_freelancer != request.user:
                self.message = "Access denied: You were not the selected freelancer for this job."
                return False
            return True

        self.message = "Access denied: You are not a participant in this chat."
        return False

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            self.message = "Authentication required: Please log in to access this chat."
            return False
        return True
    

class CanFreelancerChat(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        job_id = view.kwargs.get("job_id") or request.data.get("job")
        if not job_id:
            return False

        try:
            chat = Chat.objects.get(job__id=job_id, freelancer__user=user)
            job = chat.job
            return (
                chat.freelancer.user == user and
                job.payment_verified and
                job.selected_freelancer is not None
            )
        except Chat.DoesNotExist:
            return False


class CanAccessChat(permissions.BasePermission):
    def has_permission(self, request, view):
        # For list/create, we check permission by chat_slug later in get_chat
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        profile = request.user.profile
        # If obj is a Message, get its associated Chat; if obj is a Chat, use it directly
        chat = obj.chat if hasattr(obj, 'chat') else obj
        return (chat.client == profile or chat.freelancer == profile) and chat.active


class CanDeleteOwnMessage(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.sender == request.user


class CanReview(BasePermission):
    def has_permission(self, request, view):
        if request.method != 'POST':
            return True

        recipient_username = request.data.get('recipient')
        if not recipient_username:
            return False

        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            return False

        reviewer = request.user

        # Check if there's a Chat where reviewer is either client or freelancer with this recipient
        chats = Chat.objects.filter(
            (Q(client__user=reviewer) & Q(freelancer__user=recipient)) |
            (Q(freelancer__user=reviewer) & Q(client__user=recipient))
        )

        return chats.exists()
