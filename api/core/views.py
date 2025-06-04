from rest_framework import viewsets, status,filters,permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiResponse

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from accounts.models import Profile, FreelancerProfile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
from api.core.matching import match_freelancers_to_job, recommend_jobs_to_freelancer

from core.models import Response as JobResponse
from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView 

from api.core.serializers import ( 
    JobSerializer, ApplyResponseSerializer, ChatSerializer,
    MessageSerializer, MessageAttachmentSerializer, ReviewSerializer
)
from .permissions import (
        IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, 
        CanReview, IsResponseOwner,IsClientOfJob, 
        IsJobOwnerCanEditEvenIfAssigned
)
from django.db.models import Q

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
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsJobOwner])
    def matches(self, request, pk=None):
        job = self.get_object()
        matches = match_freelancers_to_job(job)
        return Response([{
            'freelancer': m[0].profile.user.username,
            'score': m[1],
            'skills': [s.name for s in m[0].skills.all()]
        } for m in matches])

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsJobOwner])
    def mark_completed(self, request, pk=None):
        job = self.get_object()
        job.status = 'completed'
        job.save()
        return Response({'message': 'Job marked as completed'})


class ApplyToJobView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        job = get_object_or_404(Job, slug=slug)

        if request.user.profile.user_type != 'freelancer':
            return DRFResponse({'detail': 'Only freelancers can apply.'}, status=status.HTTP_403_FORBIDDEN)

        if job.is_max_freelancers_reached:
            return DRFResponse({'detail': 'Maximum number of freelancers already applied.'}, status=status.HTTP_400_BAD_REQUEST)

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



class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated, IsChatParticipant]

    def get_queryset(self):
        return Chat.objects.filter(
            Q(client=self.request.user.profile) | Q(
                freelancer=self.request.user.profile)
        )


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsChatParticipant]

    def get_queryset(self):
        return Message.objects.filter(
            chat__in=Chat.objects.filter(
                Q(client=self.request.user.profile) | Q(
                    freelancer=self.request.user.profile)
            )
        )

    def perform_create(self, serializer):
        chat = serializer.validated_data['chat']
        job = chat.job

        # Allow only if payment is verified and freelancer selected
        if not job.payment_verified or not chat.freelancer:
            raise PermissionDenied("Chat is not active.")
        serializer.save(sender=self.request.user)


class MessageAttachmentViewSet(viewsets.ModelViewSet):
    queryset = MessageAttachment.objects.all()
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated, IsChatParticipant]

    def get_queryset(self):
        return MessageAttachment.objects.filter(
            message__chat__in=Chat.objects.filter(
                Q(client=self.request.user.profile) | Q(
                    freelancer=self.request.user.profile)
            )
        )

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        attachment = self.get_object()
        if request.user.profile not in [attachment.message.chat.client, attachment.message.chat.freelancer]:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        response = FileResponse(attachment.file)
        response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
        return response

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, CanReview]

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

    def get_queryset(self):
        recipient_id = self.request.query_params.get('recipient')
        if recipient_id:
            return Review.objects.filter(recipient_id=recipient_id)
        return Review.objects.all()

