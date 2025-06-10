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


class CanClientChat(BasePermission):
    """
    Allow only the job's client to chat if:
    - The user is the job owner
    - The job has a selected_freelancer
    - The job is payment_verified
    """

    def has_permission(self, request, view):
        user = request.user
        job_id = view.kwargs.get("job_id") or request.data.get("job")
        if not job_id:
            return False

        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return False

        # Check if the request user is the job owner (client)
        if job.client.user != user:
            return False

        # Must have selected freelancer and payment verified
        if not job.selected_freelancer or not job.payment_verified:
            return False

        # Ensure a chat exists with correct participants
        try:
            chat = Chat.objects.get(
                job=job,
                client=job.client,
                freelancer=Profile.objects.get(user=job.selected_freelancer)
            )
            return True
        except Chat.DoesNotExist:
            return False


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
