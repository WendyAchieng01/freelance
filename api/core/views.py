from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiResponse

from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.contrib.auth import get_user_model
from accounts.models import Profile, FreelancerProfile
from core.models import Job, Response, Chat, Message, MessageAttachment, Review
from api.core.matching import match_freelancers_to_job, recommend_jobs_to_freelancer
from api.core.serializers import ( 
    JobSerializer, ResponseSerializer, ChatSerializer,
    MessageSerializer, MessageAttachmentSerializer, ReviewSerializer
)
from .permissions import IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, CanReview
from django.db.models import Q

User = get_user_model()


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsClient()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsJobOwner()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(client=self.request.user.profile)

    @extend_schema(
        responses={
            200: OpenApiResponse(description="List of matched freelancers with scores")
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsJobOwner])
    def matches(self, request, pk=None):
        job = self.get_object()
        matches = match_freelancers_to_job(job)
        return Response([{
            'freelancer': m[0].profile.user.username,
            'score': m[1],
            'skills': [s.name for s in m[0].skills.all()]
        } for m in matches])

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(description="Job marked as completed"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Job not found")
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsJobOwner])
    def mark_completed(self, request, pk=None):
        job = self.get_object()
        job.status = 'completed'
        job.save()
        return Response({'message': 'Job marked as completed successfully.'})


class ResponseViewSet(viewsets.ModelViewSet):
    queryset = Response.objects.all()
    serializer_class = ResponseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsFreelancer()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsJobOwner()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Response accepted, chat created"),
            403: OpenApiResponse(description="Unauthorized")
        }
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsJobOwner])
    def accept(self, request, pk=None):
        response = self.get_object()
        job = response.job
        # Debug
        print(
            f"Accept action: user={request.user}, job.client.user={job.client.user}")
        if job.client.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        job.selected_freelancer = response.user
        job.status = 'in_progress'
        job.save()
        try:
            chat = Chat.objects.create(
                job=job,
                client=job.client,
                freelancer=response.user.profile
            )
            print(f"Chat created: id={chat.id}")  # Debug
            return Response({'message': 'Response accepted', 'chat_id': chat.id})
        except Exception as e:
            print(f"Chat creation failed: {str(e)}")  # Debug
            return Response({'error': f'Chat creation failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Response rejected"),
            403: OpenApiResponse(description="Unauthorized")
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsJobOwner])
    def reject(self, request, pk=None):
        response = self.get_object()
        job = response.job
        # Debug
        print(
            f"Reject action: user={request.user}, job.client.user={job.client.user}")
        if job.client.user != request.user:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        response.delete()
        return Response({'message': 'Response rejected'})



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
        serializer.save(sender=self.request.user)


class MessageAttachmentViewSet(viewsets.ModelViewSet):
    queryset = MessageAttachment.objects.all()
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated, IsChatParticipant]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return MessageAttachment.objects.filter(
            message__chat__in=Chat.objects.filter(
                Q(client=self.request.user.profile) | Q(
                    freelancer=self.request.user.profile)
            )
        )

    @extend_schema(
        responses={
            200: OpenApiResponse(description="File downloaded"),
            403: OpenApiResponse(description="Unauthorized")
        }
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


class FreelancerRecommendationsView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsFreelancer]

    def list(self, request):
        try:
            freelancer_profile = request.user.profile.freelancer_profile
            recommended_jobs = recommend_jobs_to_freelancer(freelancer_profile)
            serializer = JobSerializer(
                recommended_jobs, many=True, context={'request': request})
            return Response(serializer.data)
        except FreelancerProfile.DoesNotExist:
            return Response({'error': 'Freelancer profile not found'}, status=status.HTTP_404_NOT_FOUND)
