from rest_framework.throttling import ScopedRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.utils import timezone
from datetime import timedelta
from django.db import DatabaseError, IntegrityError
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics, permissions
from rest_framework import viewsets, status,filters,permissions,generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django.db import IntegrityError, DatabaseError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend


from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.db.models import Count,Prefetch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from accounts.models import Profile, FreelancerProfile
from core.models import Job, Chat, Message, MessageAttachment, Review,JobBookmark
from api.core.matching import match_freelancers_to_job, recommend_jobs_to_freelancer

from core.models import Response as JobResponse
from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView

from api.core.filters import JobFilter,AdvancedJobFilter,JobDiscoveryFilter
from api.core.serializers import ( 
    JobSerializer, ApplyResponseSerializer,ResponseListSerializer,JobWithResponsesSerializer,
    ChatSerializer, MessageSerializer, MessageAttachmentSerializer, ReviewSerializer,JobSearchSerializer,BookmarkedJobSerializer
)
from .permissions import (
        IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, 
        CanReview, IsResponseOwner,IsClientOfJob, 
        IsJobOwnerCanEditEvenIfAssigned,CanAccessChat,CanDeleteOwnMessage
)
from django.db.models import Q,F,Value, IntegerField

import logging
logger = logging.getLogger(__name__)


User = get_user_model()


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all().select_related('client', 'selected_freelancer')
    serializer_class = JobSerializer
    filter_backends = [filters.SearchFilter]
    filterset_class = JobFilter
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
        return DRFResponse({'message': 'Job marked as completed'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def aplications(self, request):
        """
        Returns all applications (responses) either submitted by the current freelancer
        or received by the current client's jobs.
        """
        user = request.user
        profile = user.profile

        if profile.user_type == 'freelancer':
            responses = JobResponse.objects.filter(user=user).select_related('job')
        elif profile.user_type == 'client':
            responses = JobResponse.objects.filter(
                job__client=profile).select_related('job')
        else:
            return DRFResponse(
                {'detail': 'Invalid user type.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ResponseListSerializer(responses, many=True)
        return DRFResponse({
            'detail': 'Job applications retrieved successfully.',
            'count': len(serializer.data),
            'applications': serializer.data
        }, status=status.HTTP_200_OK)


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
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug' 

    def get_queryset(self):
        profile = self.request.user.profile
        return Chat.objects.filter(Q(client=profile) | Q(freelancer=profile))

    def perform_create(self, serializer):
        serializer.save()
        logger.info(
            f"{self.request.user.username} created chat {serializer.instance.slug}")

    @action(detail=True, methods=['get'])
    def messages(self, request, slug=None):
        chat = self.get_object()
        if not (chat.client == request.user.profile or chat.freelancer == request.user.profile):
            raise PermissionDenied("You are not a participant in this chat.")

        messages = chat.messages.all().order_by('timestamp')
        # Mark unread messages as read
        unread_qs = messages.filter(is_read=False).exclude(sender=request.user)
        unread_qs.update(is_read=True)

        serializer = MessageSerializer(messages, many=True)
        return Response({
            'detail': 'Chat messages retrieved successfully.',
            'count': messages.count(),
            'messages': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        profile = request.user.profile
        chats = self.get_queryset()
        counts = {}

        for chat in chats:
            unread = chat.messages.filter(is_read=False).exclude(
                sender=request.user).count()
            counts[chat.slug] = unread

        return DRFResponse({
            'detail': 'Unread message counts by chat.',
            'unread_by_chat': counts
        }, status=status.HTTP_200_OK)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'

    def get_chat(self):
        chat_slug = self.kwargs.get('chat_slug')
        chat = get_object_or_404(Chat, slug=chat_slug)

        profile = self.request.user.profile
        if not (chat.client == profile or chat.freelancer == profile) or not chat.active:
            raise PermissionDenied("You do not have access to this chat.")

        return chat

    def get_queryset(self):
        chat = self.get_chat()
        messages = Message.objects.filter(chat=chat).order_by('timestamp')

        # Mark unread messages as read for this user (exclude sender's own)
        unread_qs = messages.filter(is_read=False).exclude(
            sender=self.request.user)
        unread_count = unread_qs.count()
        unread_qs.update(is_read=True)

        logger.info(
            f"{self.request.user.username} viewed messages in chat {chat.slug}. Marked {unread_count} as read.")
        return messages

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        unread_count = Message.objects.filter(
            chat=self.get_chat(),
            is_read=False
        ).exclude(sender=request.user).count()

        return DRFResponse({
            'detail': 'Messages retrieved successfully.',
            'unread_count': unread_count,
            'messages': serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        chat = self.get_chat()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(sender=request.user, chat=chat)

        logger.info(
            f"{request.user.username} sent a message in chat {chat.slug}")
        return DRFResponse({
            'detail': 'Message sent successfully.',
            'message': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sender != request.user:
            logger.warning(
                f"Unauthorized edit attempt by {request.user.username}")
            raise PermissionDenied("You can only edit your own messages.")

        serializer = self.get_serializer(
            instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"{request.user.username} updated message {instance.id}")
        return DRFResponse({
            'detail': 'Message updated successfully.',
            'message': serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.sender != request.user:
            logger.warning(
                f"Unauthorized delete attempt by {request.user.username}")
            raise PermissionDenied("You can only delete your own messages.")

        instance.delete()
        logger.info(f"{request.user.username} deleted message {instance.id}")
        return DRFResponse({'detail': 'Message deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)



class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MessageAttachment.objects.filter(message__sender=user)


class NotificationSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile

        try:
            # Count unread messages
            chat_filter = Q(client=profile) if profile.user_type == 'client' else Q(
                freelancer=profile)
            unread_messages = Message.objects.filter(chat__in=Chat.objects.filter(chat_filter)) \
                .exclude(sender=user).filter(is_read=False).count()

            # Count job responses if client
            new_responses = 0
            if profile.user_type == 'client':
                new_responses = JobResponse.objects.filter(
                    job__client=profile).count()

            # Count bookmarks if freelancer
            total_bookmarks = 0
            if profile.user_type == 'freelancer':
                total_bookmarks = JobBookmark.objects.filter(user=user).count()

            return DRFResponse({
                'detail': 'Notification summary retrieved successfully.',
                'unread_messages': unread_messages,
                'new_applications': new_responses,
                'total_bookmarks': total_bookmarks
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Notification summary failed for {user.username}: {e}")
            return DRFResponse({'error': 'Failed to retrieve notifications.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


@method_decorator(cache_page(60 * 5), name='dispatch')
class AdvancedJobSearchAPIView(generics.ListAPIView):
    serializer_class = JobSearchSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'search'

    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AdvancedJobFilter
    search_fields = ['title', 'description', 'category']
    ordering_fields = ['posted_date', 'price']
    ordering = ['-posted_date']

    def get_queryset(self):
        try:
            queryset = Job.objects.filter(status='open') \
                .select_related('client__user') \
                .prefetch_related('responses', 'bookmarked_by')

            request = self.request
            user = request.user if request.user.is_authenticated else None
            params = request.query_params

            # Bookmark filter for logged-in freelancers
            if user and params.get('bookmarked') == '1':
                queryset = queryset.filter(bookmarked_by__user=user)

            # Exclude applied jobs
            if user and params.get('exclude_applied') == '1':
                applied_job_ids = JobResponse.objects.filter(
                    user=user).values_list('job_id', flat=True)
                queryset = queryset.exclude(id__in=applied_job_ids)

            # Best match filter (skill matching)
            if user and params.get('best_match') == '1':
                try:
                    skills = user.profile.freelancer_profile.skills.values_list(
                        'name', flat=True)
                    keyword_set = set(s.lower() for s in skills)
                    score_map = {}

                    for job in queryset:
                        score = sum(1 for keyword in keyword_set
                                    if keyword in job.title.lower() or keyword in job.description.lower())
                        score_map[job.id] = score

                    queryset = sorted(queryset, key=lambda job: score_map.get(
                        job.id, 0), reverse=True)
                except Exception as e:
                    logger.warning(f"Best match logic failed: {e}")

            logger.info(
                f"Advanced search executed by: {user or 'anonymous'} | Params: {dict(params)}")
            return queryset

        except Exception as e:
            logger.error(f"Advanced job search error: {e}")
            return Job.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            response = super().list(request, *args, **kwargs)
            return DRFResponse({
                'count': self.paginator.page.paginator.count,
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
                'results': response.data
            })
        except Exception as e:
            logger.error(f"Error during job search response: {e}")
            return DRFResponse({'error': 'Unexpected search error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class JobBookmarkListView(generics.ListAPIView):
    serializer_class = BookmarkedJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JobBookmark.objects.filter(user=self.request.user).select_related('job', 'job__client')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.serializer_class(
            queryset, many=True, context={'request': request})
        return DRFResponse(serializer.data)


class AddBookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            job = get_object_or_404(Job, slug=slug)

            #  Block non-open jobs from being bookmarked
            if job.status != 'open':
                return DRFResponse({
                    'detail': f"Cannot bookmark this job. Current status is '{job.status}', only open jobs can be bookmarked."
                }, status=status.HTTP_400_BAD_REQUEST)

            bookmark, created = JobBookmark.objects.get_or_create(
                user=request.user, job=job)

            #  Check if user also applied to this job
            has_applied = job.responses.filter(user=request.user).exists()

            response_data = {
                'detail': 'Bookmarked successfully.' if created else 'Already bookmarked.',
                'bookmarked': True,
                'has_applied_and_bookmarked': has_applied,
                'job_id': job.id,
                'job_slug': job.slug
            }

            status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            logger.info(
                f"User {request.user.username} bookmarked job '{job.slug}'")

            return DRFResponse(response_data, status=status_code)

        except Exception as e:
            logger.error(f"Error bookmarking job '{slug}': {e}")
            return DRFResponse({'error': 'Failed to bookmark job.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class RemoveBookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug):
        try:
            job = get_object_or_404(Job, slug=slug)
            deleted, _ = JobBookmark.objects.filter(
                user=request.user, job=job).delete()
            if deleted:
                logger.info(
                    f"User {request.user.username} removed bookmark for job '{job.slug}'")
                return DRFResponse({'detail': 'Bookmark removed.'}, status=status.HTTP_200_OK)
            else:
                logger.warning(
                    f"User {request.user.username} tried to remove nonexistent bookmark for job '{job.slug}'")
                return DRFResponse({'detail': 'Bookmark did not exist.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error removing bookmark for job '{slug}': {e}")
            return DRFResponse({'error': 'Failed to remove bookmark.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobsByClientView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        query_mode = request.query_params.get('query', 'mine')
        status_filter = request.query_params.get('status')

        if query_mode == 'all':
            return self._handle_public_open_jobs(request, status_filter)

        return self._handle_logged_in_client_jobs(request, status_filter)

    def _handle_logged_in_client_jobs(self, request, status_filter=None):
        try:
            if not request.user.is_authenticated:
                return DRFResponse({
                    'success': False,
                    'message': 'Authentication required to access your posted jobs.'
                }, status=status.HTTP_401_UNAUTHORIZED)

            if not hasattr(request.user, 'profile') or request.user.profile.user_type != 'client':
                return DRFResponse({
                    'success': False,
                    'message': 'You must be a client to access your posted jobs.'
                }, status=status.HTTP_403_FORBIDDEN)

            profile = request.user.profile
            jobs = Job.objects.filter(client=profile).select_related('client')

            if status_filter in ['open', 'in_progress', 'completed']:
                jobs = jobs.filter(status=status_filter)

            job_count = jobs.count()
            if job_count == 0:
                return DRFResponse({
                    'success': True,
                    'message': 'You have not posted any jobs yet.',
                    'client': {
                        'username': request.user.username,
                        'email': request.user.email,
                        'bio': getattr(profile, 'bio', ''),
                        'location': getattr(profile, 'location', ''),
                        'profile_pic': profile.profile_pic.url if profile.profile_pic else None
                    },
                    'job_count': 0,
                    'jobs': []
                })

            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serialized_jobs = JobSearchSerializer(
                paginated_jobs, many=True).data

            return paginator.get_paginated_response({
                'success': True,
                'message': 'Your posted jobs were retrieved successfully.',
                'client': {
                    'username': request.user.username,
                    'email': request.user.email,
                    'bio': getattr(profile, 'bio', ''),
                    'location': getattr(profile, 'location', ''),
                    'profile_pic': profile.profile_pic.url if profile.profile_pic else None
                },
                'job_count': job_count,
                'jobs': serialized_jobs
            })

        except Exception as e:
            logger.error(f"Error fetching logged-in client jobs: {e}")
            return DRFResponse({
                'success': False,
                'message': 'An error occurred while fetching your jobs.',
                'jobs': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_public_open_jobs(self, request, status_filter=None):
        try:
            jobs = Job.objects.select_related('client')

            if status_filter in ['open', 'in_progress', 'completed']:
                jobs = jobs.filter(status=status_filter)
            else:
                jobs = jobs.filter(status='open')

            jobs = jobs.annotate(job_count=Count('client__jobs'))

            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_jobs = paginator.paginate_queryset(jobs, request)
            serialized_jobs = JobSearchSerializer(
                paginated_jobs, many=True).data

            return paginator.get_paginated_response({
                'success': True,
                'message': 'Public job listing: all jobs from all clients.',
                'job_count': jobs.count(),
                'jobs': serialized_jobs
            })

        except Exception as e:
            logger.error(f"Error fetching public open jobs: {e}")
            return DRFResponse({
                'success': False,
                'message': 'Failed to retrieve public job listings.',
                'jobs': []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FreelancerJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, status_filter):
        user = request.user
        profile = user.profile

        if profile.user_type != 'freelancer':
            return DRFResponse({'detail': 'Only freelancers can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)

        # Normalize 'active' to 'in_progress'
        if status_filter == 'active':
            status_filter = 'in_progress'

        # Case: applied jobs
        if status_filter == 'applied':
            jobs = Job.objects.filter(responses__user=user).distinct()
            serializer = JobSearchSerializer(jobs, many=True)
            return DRFResponse({'status': 'applied', 'count': len(serializer.data), 'jobs': serializer.data}, status=200)
        
        elif status_filter == 'rejected':
            # Jobs the freelancer applied to, but was NOT selected
            jobs = Job.objects.filter(
                responses__user=user
            ).exclude(
                selected_freelancer=user
            ).distinct()

            serializer = JobSearchSerializer(jobs, many=True)
            logger.info(f"{user.username} fetched rejected jobs.")
            return DRFResponse({
                'status': 'rejected',
                'count': len(serializer.data),
                'jobs': serializer.data
            }, status=status.HTTP_200_OK)

        # Case: active (in_progress) or completed
        elif status_filter in ['in_progress', 'completed']:
            jobs = Job.objects.filter(
                selected_freelancer=user, status=status_filter)
            serializer = JobSearchSerializer(jobs, many=True)
            return DRFResponse({'status': status_filter, 'count': len(serializer.data), 'jobs': serializer.data}, status=200)

        # Case: open jobs → return open jobs + bookmark flag
        elif status_filter == 'open':
            jobs = Job.objects.filter(status='open')
            # Fetch all bookmarked job IDs for the current user
            bookmarked_ids = set(user.bookmarks.values_list('job_id', flat=True))
            
            applied_ids = set(JobResponse.objects.filter(user=user).values_list('job_id', flat=True))

            results = []
            for job in jobs:
                job_data = JobSearchSerializer(job).data
                job_data['bookmarked'] = job.id in bookmarked_ids
                job_data['has_applied'] = job.id in applied_ids
                job_data['has_applied_and_bookmarked'] = job.id in bookmarked_ids and job.id in applied_ids
                job_data['open'] = True
                results.append(job_data)

            return DRFResponse({'status': 'open', 'count': len(results), 'jobs': results}, status=200)

        else:
            return DRFResponse({'detail': 'Invalid status filter. Use applied, active, completed, or open.'},
                               status=status.HTTP_400_BAD_REQUEST)
    
    
class ClientJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, status_filter):
        user = request.user
        profile = user.profile

        if profile.user_type != 'client':
            return DRFResponse({'detail': 'Only clients can access this endpoint.'}, status=status.HTTP_403_FORBIDDEN)

        # frontend's `active` → `in_progress`
        if status_filter == 'active':
            status_filter = 'in_progress'

        if status_filter in ['open', 'in_progress', 'completed']:
            jobs = Job.objects.filter(client=profile, status=status_filter)
            serializer = JobSearchSerializer(jobs, many=True)
            logger.info(
                f"{user.username} fetched client {status_filter} jobs.")
            return DRFResponse({
                'status': status_filter,
                'count': len(serializer.data),
                'jobs': serializer.data
            }, status=status.HTTP_200_OK)

        elif status_filter == 'applied':
            responses = JobResponse.objects.filter(
                job__client=profile).select_related('job', 'user')
            serializer = ResponseListSerializer(responses, many=True)
            logger.info(f"{user.username} fetched client applications.")
            return DRFResponse({
                'status': 'applied',
                'count': len(serializer.data),
                'applications': serializer.data
            }, status=status.HTTP_200_OK)
        
        elif status_filter == 'rejected':
            # Responses where the applicant is NOT the selected freelancer
            responses = JobResponse.objects.filter(
                job__client=profile
            ).exclude(
                user=F('job__selected_freelancer')
            ).select_related('user', 'job')

            serializer = ResponseListSerializer(responses, many=True)
            logger.info(f"{user.username} fetched rejected freelancers.")
            return DRFResponse({
                'status': 'rejected',
                'count': len(serializer.data),
                'rejected_applicants': serializer.data
            }, status=status.HTTP_200_OK)

        else:
            return DRFResponse({
                'detail': 'Invalid status filter. Use open, in_progress, completed, applied.'
            }, status=status.HTTP_400_BAD_REQUEST)


class JobDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile

        try:
            data = {}

            if profile.user_type == 'client':
                jobs = Job.objects.filter(client=profile)
                data = {
                    'total_jobs': jobs.count(),
                    'open_jobs': jobs.filter(status='open').count(),
                    'in_progress_jobs': jobs.filter(status='in_progress').count(),
                    'completed_jobs': jobs.filter(status='completed').count(),
                    'total_responses': JobResponse.objects.filter(job__client=profile).count()
                }

            elif profile.user_type == 'freelancer':
                data = {
                    'applied_jobs': JobResponse.objects.filter(user=user).count(),
                    'assigned_jobs': Job.objects.filter(selected_freelancer=user).count(),
                    'completed_jobs': Job.objects.filter(selected_freelancer=user, status='completed').count(),
                    'bookmarked_jobs': JobBookmark.objects.filter(user=user).count()
                }

            logger.info(f"{user.username} fetched dashboard summary.")

            return DRFResponse({
                'detail': 'Dashboard summary retrieved successfully.',
                'summary': data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in dashboard summary for {user.username}: {e}")
            return DRFResponse({
                'error': 'Failed to retrieve dashboard summary.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class JobDiscoveryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    

class JobDiscoveryView(APIView):
    permission_classes = [AllowAny]
    pagination_class = JobDiscoveryPagination

    def get(self, request, status_filter=None):
        user = request.user if request.user.is_authenticated else None

        try:
            jobs = Job.objects.filter(
                status='open').select_related('client__user')

            # Filters
            category = request.query_params.get('category')
            level = request.query_params.get('preferred_freelancer_level')

            if category:
                jobs = jobs.filter(category__iexact=category)

            if level:
                jobs = jobs.filter(preferred_freelancer_level__iexact=level)

            # Bookmark and applied data
            bookmarked_ids = set()
            applied_ids = set()

            if user:
                bookmarked_ids = set(
                    JobBookmark.objects.filter(
                        user=user).values_list('job_id', flat=True)
                )
                applied_ids = set(
                    JobResponse.objects.filter(
                        user=user).values_list('job_id', flat=True)
                )

            # Status filter logic
            now = timezone.now()

            if status_filter == 'best_match':
                if not user or not hasattr(user, 'profile') or not hasattr(user.profile, 'freelancer_profile'):
                    return DRFResponse({
                        'success': False,
                        'message': 'Authentication required for best_match filter.',
                        'status_code': status.HTTP_403_FORBIDDEN
                    }, status=status.HTTP_403_FORBIDDEN)

                skill_names = user.profile.freelancer_profile.skills.values_list(
                    'name', flat=True)
                jobs = list(jobs)

                def match_score(job):
                    return sum(
                        1 for skill in skill_names if skill.lower() in (job.title + job.description).lower()
                    )

                jobs = sorted(jobs, key=match_score, reverse=True)

            elif status_filter == 'most_recent':
                jobs = jobs.order_by('-posted_date')

            elif status_filter == 'trending':
                jobs = jobs.annotate(application_count=Count(
                    'responses')).order_by('-application_count')

            elif status_filter == 'near_deadline':
                jobs = jobs.order_by('deadline_date')

            elif status_filter in [None, '', 'open']:
                jobs = jobs.order_by('-posted_date')

            else:
                return DRFResponse({
                    'success': False,
                    'message': f"Invalid status_filter '{status_filter}'. Use one of: best_match, most_recent, trending, near_deadline, open.",
                    'status_code': status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)

            # Serialize and enrich
            results = []
            for job in jobs:
                data = JobSearchSerializer(job).data
                job_id = job.id
                data['bookmarked'] = job_id in bookmarked_ids
                data['has_applied'] = job_id in applied_ids
                data['has_applied_and_bookmarked'] = job_id in bookmarked_ids and job_id in applied_ids
                results.append(data)

            # Paginate
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(results, request)
            return paginator.get_paginated_response({
                'success': True,
                'status_filter': status_filter or 'open',
                'count': len(results),
                'message': 'Jobs fetched successfully.',
                'status_code': status.HTTP_200_OK,
                'jobs': page
            })

        except Exception as e:
            return DRFResponse({
                'success': False,
                'message': f"An unexpected error occurred: {str(e)}",
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
