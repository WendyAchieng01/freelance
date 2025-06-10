import logging
from django.db import DatabaseError, IntegrityError
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics, permissions
from rest_framework import viewsets, status,filters,permissions,generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import IntegrityError, DatabaseError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.db.models import Count,Prefetch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from accounts.models import Profile, FreelancerProfile
from core.models import Job, Chat, Message, MessageAttachment, Review
from api.core.matching import match_freelancers_to_job, recommend_jobs_to_freelancer

from core.models import Response as JobResponse
from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView

from api.core.serializers import ( 
    JobSerializer, ApplyResponseSerializer,ResponseListSerializer,JobWithResponsesSerializer,
    ChatSerializer, MessageSerializer, MessageAttachmentSerializer, ReviewSerializer
)
from .permissions import (
        IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, 
        CanReview, IsResponseOwner,IsClientOfJob, 
        IsJobOwnerCanEditEvenIfAssigned,CanAccessChat,CanDeleteOwnMessage
)
from django.db.models import Q

logger = logging.getLogger(__name__)


User = get_user_model()


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all().select_related('client', 'selected_freelancer')
    serializer_class = JobSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'category']
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        if self.action == 'create':
            return [IsAuthenticated(), IsClient()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsJobOwner()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user.profile)

    def perform_update(self, serializer):
        job = self.get_object()
        if job.selected_freelancer:
            raise ValidationError(
                "You cannot modify a job after it has been assigned.")
        serializer.save()

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsClient])
    def my_jobs(self, request):
        jobs = self.queryset.filter(client__user=request.user)
        serializer = self.get_serializer(jobs, many=True)
        return DRFResponse(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsJobOwner])
    def matches(self, request, pk=None):
        job = self.get_object()
        matches = match_freelancers_to_job(job)
        return DRFResponse([{
            'freelancer': m[0].profile.user.username,
            'score': m[1],
            'skills': [s.name for s in m[0].skills.all()]
        } for m in matches])

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsJobOwner])
    def mark_completed(self, request, pk=None):
        job = self.get_object()
        job.status = 'completed'
        job.save()
        return DRFResponse({'message': 'Job marked as completed'})


class ApplyToJobView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        if request.user.profile.user_type != 'freelancer':
            return DRFResponse({'detail': 'Only freelancers can apply.'}, status=status.HTTP_403_FORBIDDEN)

        if job.is_max_freelancers_reached:
            return DRFResponse({'detail': 'Maximum number of freelancers already applied.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if job.selected_freelancer:
            return DRFResponse({'error': 'A freelancer has already been accepted and only one freelancer is needed'}, status=status.HTTP_423_LOCKED)

        if JobResponse.objects.filter(job=job, user=request.user).exists():
            return DRFResponse({'detail': 'You have already applied to this job.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ApplyResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job_response = JobResponse.objects.create(
            job=job,
            user=request.user,
            extra_data=serializer.validated_data.get('extra_data', None)
        )

        response_serializer = ApplyResponseSerializer(job_response)
        return DRFResponse({'detail': 'Successfully applied.', 'data': response_serializer.data}, status=status.HTTP_201_CREATED)


class UnapplyFromJobView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        if request.user.profile.user_type != 'freelancer':
            return DRFResponse({'detail': 'Only freelancers can unapply.'}, status=status.HTTP_403_FORBIDDEN)

        response = JobResponse.objects.filter(
            job=job, user=request.user).first()
        if not response:
            return DRFResponse({'detail': 'You have not applied to this job.'}, status=status.HTTP_400_BAD_REQUEST)

        response.delete()
        return DRFResponse({'detail': 'Successfully removed your application.'}, status=status.HTTP_204_NO_CONTENT)


class ResponseListForJobView(generics.ListAPIView):
    serializer_class = ResponseListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        slug = self.kwargs.get('slug', None)

        if slug:
            job = get_object_or_404(Job, slug=slug)
            if job.client.user != user:
                raise PermissionDenied("You do not own this job.")
            return JobResponse.objects.filter(job=job)
        else:
            # List all responses for all jobs owned by this user
            return JobResponse.objects.filter(job__client__user=user).distinct()


class JobsWithResponsesView(generics.ListAPIView):
    serializer_class = JobWithResponsesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(
            client__user=self.request.user,
            responses__isnull=False
        ).distinct().prefetch_related(
            Prefetch('responses', queryset=JobResponse.objects.select_related('user'))
        )
            

class AcceptFreelancerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug, identifier):
        job = get_object_or_404(Job, slug=slug)

        # Check if the requester is the job owner
        if job.client.user != request.user:
            return DRFResponse({'detail': 'You are not the owner of this job.'}, status=status.HTTP_403_FORBIDDEN)

        # Try to resolve identifier to a User (username first, then ID)
        freelancer = User.objects.filter(username=identifier).first(
        ) or User.objects.filter(id__iexact=identifier).first()
        if not freelancer:
            return DRFResponse({'error': 'Freelancer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure this freelancer actually applied to the job
        if not JobResponse.objects.filter(job=job, user=freelancer).exists():
            return DRFResponse({'error': 'This freelancer did not apply to this job.'}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure no freelancer is already selected
        if job.selected_freelancer:
            return DRFResponse({'error': 'A freelancer has already been accepted for this job.'}, status=status.HTTP_400_BAD_REQUEST)

        # Accept the freelancer
        job.selected_freelancer = freelancer
        job.status = 'in_progress'
        job.save()

        return DRFResponse({'message': f'{freelancer.username} has been accepted for this job.'}, status=status.HTTP_200_OK)


class RejectFreelancerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug, identifier):
        job = get_object_or_404(Job, slug=slug)

        if job.client.user != request.user:
            return DRFResponse({'detail': 'You are not the owner of this job.'}, status=status.HTTP_403_FORBIDDEN)

        freelancer = User.objects.filter(username=identifier).first(
        ) or User.objects.filter(id__iexact=identifier).first()
        if not freelancer:
            return DRFResponse({'error': 'Freelancer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if job.selected_freelancer != freelancer:
            return DRFResponse({'error': 'This freelancer is not currently selected for this job.'}, status=status.HTTP_400_BAD_REQUEST)

        job.selected_freelancer = None
        job.status = 'open'
        job.save()

        return DRFResponse({'message': f'{freelancer.username} has been unassigned from this job.'}, status=status.HTTP_200_OK)


class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessChat]

    def get_queryset(self):
        profile = self.request.user.profile
        return Chat.objects.filter(Q(client=profile) | Q(freelancer=profile))

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        chat = self.get_object()
        messages = chat.messages.all()
        serializer = MessageSerializer(messages, many=True)
        return DRFResponse(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessChat]

    def get_chat(self):
        chat_slug = self.kwargs.get('chat_slug')
        chat = get_object_or_404(Chat, slug=chat_slug)
        # check if user is participant and chat is active
        profile = self.request.user.profile
        if not (chat.client == profile or chat.freelancer == profile) or not chat.active:
            raise PermissionDenied("You do not have access to this chat.")
        return chat

    def get_queryset(self):
        chat = self.get_chat()
        return Message.objects.filter(chat=chat).order_by('timestamp')

    def perform_create(self, serializer):
        chat = self.get_chat()
        # auto-set sender to logged in user and link message to chat
        serializer.save(sender=self.request.user, chat=chat)

    def perform_update(self, serializer):
        message = self.get_object()
        if message.sender != self.request.user:
            raise PermissionDenied("You can only edit your own messages.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.sender != self.request.user:
            raise PermissionDenied("You can only delete your own messages.")
        instance.delete()

class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MessageAttachment.objects.filter(message__sender=user)




class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, CanReview]

    def get_queryset(self):
        recipient_id = self.request.query_params.get('recipient')
        if recipient_id:
            return Review.objects.filter(recipient_id=recipient_id)
        return Review.objects.all()

    def perform_create(self, serializer):
        try:
            serializer.save(reviewer=self.request.user)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error during review creation: {e}")
            raise serializers.ValidationError(
                {"detail": f"Database error while saving review: {str(e)}"})
