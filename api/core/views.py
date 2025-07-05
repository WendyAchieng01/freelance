from drf_spectacular.utils import extend_schema_field, OpenApiTypes, OpenApiResponse, extend_schema, OpenApiParameter, OpenApiRequest, extend_schema_view
from rest_framework.throttling import ScopedRateThrottle
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db import DatabaseError, IntegrityError
from rest_framework.exceptions import PermissionDenied,NotFound,ValidationError
from rest_framework import generics, permissions
from rest_framework import viewsets, status,filters,permissions,generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from django.db import IntegrityError, DatabaseError
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend


from django.shortcuts import get_object_or_404,redirect
from django.http import FileResponse
from django.db.models import Count,Prefetch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from accounts.models import Profile, FreelancerProfile,Skill
from core.models import Job, JobCategory,Chat, Message, MessageAttachment, Review,JobBookmark,Notification,Response as JobResponse
from api.core.matching import match_freelancers_to_job, recommend_jobs_to_freelancer
from api.wallet.utility import get_wallet_stats

from rest_framework.response import Response as DRFResponse
from rest_framework.views import APIView

from api.core.filters import JobFilter,AdvancedJobFilter,JobDiscoveryFilter,get_job_filters
from api.core.serializers import ( 
    JobSerializer,JobCategorySerializer, ApplyResponseSerializer,ResponseListSerializer,JobWithResponsesSerializer,NotificationSerializer,
    ChatSerializer, MessageSerializer, MessageAttachmentSerializer, ReviewSerializer,JobSearchSerializer,BookmarkedJobSerializer
)
from .permissions import (
        IsClient, IsFreelancer, IsJobOwner, IsChatParticipant, 
        CanReview, IsResponseOwner,IsClientOfJob, 
        IsJobOwnerCanEditEvenIfAssigned,CanAccessChat,CanDeleteOwnMessage
        
)
from django.db.models import Q,F,Value, IntegerField,Sum

import logging
from datetime import timedelta
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)


User = get_user_model()


class CustomPaginator(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema(
    summary="List all job categories or create a new one",
    description="GET returns a list of all job categories. POST allows clients to create a new category by name.",
    request=JobCategorySerializer,
    responses={
        200: JobCategorySerializer(many=True),
        201: OpenApiResponse(description="Category created successfully."),
        400: OpenApiResponse(description="Invalid input data."),
        403: OpenApiResponse(description="Authentication required to create.")
    }
)
class JobCategoryListCreateView(generics.ListCreateAPIView):
    queryset = JobCategory.objects.all().order_by('name')
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


@extend_schema(
    summary="Retrieve, update, or delete a job category",
    description="Handles individual category retrieval, update, or deletion by slug.",
    responses={
        200: JobCategorySerializer,
        204: OpenApiResponse(description="Deleted successfully."),
        400: OpenApiResponse(description="Bad request."),
        404: OpenApiResponse(description="Category not found."),
        403: OpenApiResponse(description="Authentication required.")
    }
)
class JobCategoryRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobCategory.objects.all()
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug' 



@extend_schema_field(OpenApiTypes.STR)
def get_skills_required_choices():
    return [choice[0] for choice in Skill.SKILL_CHOICES]



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
        
    @extend_schema(
        summary="Create a new job",
        description="Clients can post a new job. Skills and category are created if they don’t exist.",
        request=JobSerializer,
        responses={
            201: OpenApiResponse(response=JobSerializer, description="Job created successfully."),
            400: OpenApiResponse(description="Invalid data."),
            403: OpenApiResponse(description="Only clients can create jobs.")
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="List all jobs",
        description="Returns a paginated list of all jobs. Search and filter available.",
        responses={
            200: OpenApiResponse(response=JobSerializer(many=True), description="List of jobs")
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve job details",
        description="Returns full job details including client, selected freelancer, skills, responses, and reviews.",
        responses={
            200: OpenApiResponse(response=JobSerializer),
            404: OpenApiResponse(description="Job not found.")
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update a job",
        description="Clients can update jobs that have no selected freelancer.",
        request=JobSerializer,
        responses={
            200: OpenApiResponse(response=JobSerializer),
            400: OpenApiResponse(description="Cannot update a job once a freelancer is selected."),
            403: OpenApiResponse(description="Only the job owner can update."),
            404: OpenApiResponse(description="Job not found.")
        }
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a job",
        description="Only job owners can delete jobs. Cannot delete if a freelancer is already selected.",
        responses={
            204: OpenApiResponse(description="Job deleted successfully."),
            403: OpenApiResponse(description="Only the job owner can delete."),
            404: OpenApiResponse(description="Job not found.")
        }
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    
    @extend_schema(
        summary="List jobs created by current client",
        description="Returns a list of jobs posted by the authenticated client.",
        responses={
            200: OpenApiResponse(response=JobSerializer(many=True)),
            403: OpenApiResponse(description="Only clients can view their jobs.")
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsClient])
    def my_jobs(self, request):
        jobs = self.queryset.filter(client__user=request.user)
        serializer = self.get_serializer(jobs, many=True)
        return DRFResponse(serializer.data)

    @extend_schema(
        summary="Match freelancers to a job",
        description="Returns a ranked list of freelancers matched to this job based on skills.",
        responses={
            200: OpenApiResponse(description="Matching freelancers with score and skills."),
            403: OpenApiResponse(description="Only the job owner can access matches."),
            404: OpenApiResponse(description="Job not found.")
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsJobOwner])
    def matches(self, request, pk=None):
        job = self.get_object()
        matches = match_freelancers_to_job(job)
        return DRFResponse([{
            'freelancer': m[0].profile.user.username,
            'score': m[1],
            'skills': [s.name for s in m[0].skills.all()]
        } for m in matches])

    @extend_schema(
        summary="Mark a job as completed",
        description="Marks the job as completed if it's in progress and a freelancer has been selected.",
        responses={
            200: OpenApiResponse(description="Job marked as completed successfully."),
            400: OpenApiResponse(description="Job could not be marked as completed."),
            403: OpenApiResponse(description="Only the job owner can perform this action.")
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsJobOwner])
    def mark_completed(self, request, slug=None):
        job = self.get_object()

        success = job.mark_as_completed()

        if success:
            return DRFResponse(
                {'detail': 'Job marked as completed successfully.'},
                status=status.HTTP_200_OK
            )
        else:
            return DRFResponse(
                {'detail': 'Job could not be marked as completed. Ensure it is in progress, has a selected freelancer, and payment is verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="List job applications",
        description="Returns all job applications submitted by the freelancer or received by the client.",
        responses={
            200: OpenApiResponse(
                description="List of job applications",
                response=ResponseListSerializer(many=True)
            ),
            400: OpenApiResponse(description="Invalid user type."),
            403: OpenApiResponse(description="Authentication required.")
        }
    )
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
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Apply to a job",
        description="Submit an application to a job with optional CV, cover letter, and portfolio.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "extra_data": {
                        "type": "string",
                        "format": "json",
                        "description": "Optional JSON data (e.g., {\"note\": \"Available\"})"
                    },
                    "cv": {
                        "type": "string",
                        "format": "binary",
                        "description": "CV file (PDF, DOC, DOCX)"
                    },
                    "cover_letter": {
                        "type": "string",
                        "format": "binary",
                        "description": "Cover letter file"
                    },
                    "portfolio": {
                        "type": "string",
                        "format": "binary",
                        "description": "Portfolio file (PDF or images)"
                    },
                },
                "required": []
            }
        },
        responses={
            201: OpenApiResponse(description="Application submitted successfully."),
            400: OpenApiResponse(description="Bad request (e.g. duplicate application)."),
            403: OpenApiResponse(description="Only freelancers can apply.")
        }
    )
    


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


@extend_schema(
    summary="Unapply from a job",
    description="Allows a freelancer to withdraw their application to a job by its slug.",
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                         description='Slug of the job', required=True, type=str)
    ],
    responses={
        204: OpenApiResponse(description="Successfully removed your application."),
        400: OpenApiResponse(description="No existing application found."),
        403: OpenApiResponse(description="Only freelancers can unapply."),
        404: OpenApiResponse(description="Job not found.")
    }
)
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
    

@extend_schema(
    summary="Update application files",
    description="Allows a freelancer to update their submitted CV, cover letter, or portfolio for a specific job application.",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "cv": {
                    "type": "string",
                    "format": "binary",
                    "description": "Updated CV file"
                },
                "cover_letter": {
                    "type": "string",
                    "format": "binary",
                    "description": "Updated cover letter file"
                },
                "portfolio": {
                    "type": "string",
                    "format": "binary",
                    "description": "Updated portfolio file"
                },
            },
            "required": []
        }
    },
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                         description='Slug of the job', required=True, type=str)
    ],
    responses={
        200: OpenApiResponse(description="Files updated successfully.", response=ApplyResponseSerializer),
        400: OpenApiResponse(description="Invalid input or file format."),
        403: OpenApiResponse(description="Authentication required."),
        404: OpenApiResponse(description="You have not applied to this job.")
    }
)
class UpdateResponseFilesView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug):
        job = get_object_or_404(Job, slug=slug)
        try:
            response = JobResponse.objects.get(job=job, user=request.user)
        except JobResponse.DoesNotExist:
            return DRFResponse({'detail': 'You have not applied to this job.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApplyResponseSerializer(
            response, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return DRFResponse({
            'detail': 'Files updated successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


@extend_schema(
    summary="Get responses for a job",
    description="""
Returns job applications based on user type:
- **Client:** Gets all responses submitted for their job.
- **Freelancer:** Gets their own submitted response if they applied.
""",
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                         description='Slug of the job', required=True, type=str)
    ],
    responses={
        200: OpenApiResponse(description="Applications fetched successfully.", response=ResponseListSerializer),
        400: OpenApiResponse(description="Invalid user profile."),
        403: OpenApiResponse(description="Unauthorized access."),
        404: OpenApiResponse(description="Job not found or freelancer did not apply.")
    }
)
class ResponseListForJobView(generics.GenericAPIView):
    serializer_class = ResponseListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get(self, request, slug=None):
        user = request.user
        job = get_object_or_404(Job, slug=slug)

        if not hasattr(user, 'profile'):
            return DRFResponse(
                {"detail": "Invalid user profile."},
                status=status.HTTP_400_BAD_REQUEST
            )

        role = user.profile.user_type

        if role == 'client':
            if job.client.user != user:
                return DRFResponse(
                    {"detail": "You do not own this job."},
                    status=status.HTTP_403_FORBIDDEN
                )

            responses = JobResponse.objects.filter(job=job)
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(responses, request)
            serializer = self.get_serializer(page, many=True)

            return paginator.get_paginated_response({
                "job": JobSerializer(job, context={"request": request}).data,
                "applications": serializer.data
            })

        elif role == 'freelancer':
            try:
                response = JobResponse.objects.get(job=job, user=user)
            except JobResponse.DoesNotExist:
                return DRFResponse(
                    {"detail": "You have not applied to this job."},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = self.get_serializer(response)
            return DRFResponse({
                "job": JobSerializer(job, context={"request": request}).data,
                "application": serializer.data
            }, status=status.HTTP_200_OK)

        return DRFResponse(
            {"detail": "Unsupported user type."},
            status=status.HTTP_403_FORBIDDEN
        )


@extend_schema(
    summary="List jobs with responses",
    description="Returns all jobs owned by the authenticated client that have at least one response (application).",
    responses={
        200: OpenApiResponse(description="Jobs with responses fetched successfully.", response=JobWithResponsesSerializer(many=True)),
        403: OpenApiResponse(description="Authentication credentials were not provided.")
    }
)
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
            

@extend_schema(
    summary="Accept a freelancer for a job",
    description="""
Assigns a freelancer to a job, marks it as in-progress, and ensures:
- The requesting user owns the job.
- The freelancer applied to the job.
- Payment has been verified.
""",
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                         description='Slug of the job', required=True, type=str),
        OpenApiParameter(name='identifier', location=OpenApiParameter.PATH,
                         description='Username or ID of the freelancer', required=True, type=str)
    ],
    responses={
        200: OpenApiResponse(description="Freelancer accepted successfully."),
        400: OpenApiResponse(description="Freelancer did not apply or one is already selected."),
        403: OpenApiResponse(description="User is not job owner."),
        404: OpenApiResponse(description="Job or freelancer not found.")
    }
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
        
        if job.payment_verified:

            # Accept the freelancer
            job.selected_freelancer = freelancer
            job.status = 'in_progress'
            job.save()
        
        else:
            return DRFResponse({'message': f'{request.user.username} You can only accept a client after making the full deposit.'}, status=status.HTTP_200_OK)

        return DRFResponse({'message': f'{freelancer.username} has been accepted for this job.'}, status=status.HTTP_200_OK)


@extend_schema(
    summary="Unassign freelancer from job --> Application Rejected",
    description="Allows the client to remove a previously accepted freelancer from their job.",
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                            description='Slug of the job', required=True, type=str),
        OpenApiParameter(name='identifier', location=OpenApiParameter.PATH,
                            description='Username or ID of the freelancer', required=True, type=str)
    ],
    responses={
        200: OpenApiResponse(description="Freelancer unassigned successfully."),
        400: OpenApiResponse(description="Freelancer was not selected."),
        403: OpenApiResponse(description="User is not job owner."),
        404: OpenApiResponse(description="Job or freelancer not found.")
    }
)
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


@extend_schema(
    summary="Notification summary",
    description="""
        Returns a summary of:
        - Unread messages (excluding current users own messages).
        - Job applications (for clients).
        - Bookmarked jobs (for freelancers).
        """,
    responses={
        200: OpenApiResponse(description="Summary of notifications."),
        403: OpenApiResponse(description="Authentication credentials were not provided."),
        500: OpenApiResponse(description="Failed to retrieve notifications.")
    }
)
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



@method_decorator(cache_page(60 * 5), name='dispatch')
class AdvancedJobSearchAPIView(generics.ListAPIView):
    serializer_class = JobSearchSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'search'

    filter_backends = [DjangoFilterBackend,filters.SearchFilter, filters.OrderingFilter]
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


@extend_schema(
    summary="List bookmarked jobs for the authenticated user",
    description="Returns paginated bookmarked jobs by the current authenticated user (freelancer).",
    responses={
        200: OpenApiResponse(description="List of bookmarked jobs.", response=BookmarkedJobSerializer(many=True)),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    tags=["Jobs", "Bookmarks"]
)
class JobBookmarkListView(generics.ListAPIView):
    serializer_class = BookmarkedJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPaginator

    def get_queryset(self):
        return JobBookmark.objects.filter(user=self.request.user).select_related('job', 'job__client')


@extend_schema(
    summary="Add a bookmark to a job",
    description="""
            Allows an authenticated freelancer to bookmark an open job.
            - Only jobs with status 'open' can be bookmarked.
            - Returns if bookmark was created or already exists.
            - Also indicates if user has applied to the job.
            """,
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                            description='Job slug to bookmark', required=True, type=str)
    ],
    request=None,
    responses={
        201: OpenApiResponse(description="Bookmark created successfully."),
        200: OpenApiResponse(description="Job was already bookmarked."),
        400: OpenApiResponse(description="Job is not open for bookmarking."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        500: OpenApiResponse(description="Failed to bookmark job."),
    },
    tags=["Jobs", "Bookmarks"]
)
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


@extend_schema(
    summary="Remove a bookmark from a job",
    description="Allows an authenticated freelancer to remove a bookmark from a job if it exists.",
    parameters=[
        OpenApiParameter(name='slug', location=OpenApiParameter.PATH,
                         description='Job slug to remove bookmark from', required=True, type=str)
    ],
    request=None,
    responses={
        200: OpenApiResponse(description="Bookmark removed successfully."),
        404: OpenApiResponse(description="Bookmark did not exist."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
        500: OpenApiResponse(description="Failed to remove bookmark."),
    },
    tags=["Jobs", "Bookmarks"]
)
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


@extend_schema(
    summary="Freelancer Job Status Overview",
    description="""
        Get jobs filtered by status for the authenticated freelancer.
        Supports filters for:
        - status: applied, rejected, selected, in_progress, completed, open
        - ordering by posted date or other fields
        Returns job listings along with stats (application counts, rejections, active, completed, bookmarks).
        """,
    parameters=[
        OpenApiParameter(name='status', description="Job status filter", required=False,
                            type=str, enum=['applied', 'rejected', 'selected', 'in_progress', 'completed', 'open']),
        OpenApiParameter(
            name='ordering', description="Order jobs by field (e.g. -posted_date)", required=False, type=str),
        OpenApiParameter(
            name='page', description="Page number for pagination", required=False, type=int),
    ],
    responses={
        200: OpenApiResponse(description="Paginated job list with freelancer status summary"),
        400: OpenApiResponse(description="Invalid status filter or request"),
        403: OpenApiResponse(description="Access denied for non-freelancers"),
    },
    tags=["Jobs", "Freelancer"]
)
class FreelancerJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile
        if profile.user_type != 'freelancer':
            return DRFResponse({'detail': 'Only freelancers can access this endpoint.'},
                            status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get('status')
        if status_filter == 'active':
            status_filter = 'in_progress'

        try:
            filters = get_job_filters(request)
        except ValueError as e:
            return DRFResponse({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ordering = request.query_params.get('ordering', '-posted_date')
        paginator = PageNumberPagination()
        paginator.page_size = 10

        bookmarked_ids = set(user.bookmarks.values_list('job_id', flat=True))
        applied_ids = set(JobResponse.objects.filter(
            user=user).values_list('job_id', flat=True))

        base_queryset = Job.objects.filter(Q(responses__user=user) | Q(
            id__in=bookmarked_ids)).filter(filters).distinct()
        total_applied = base_queryset.filter(responses__user=user).count()
        total_bookmarked = base_queryset.filter(id__in=bookmarked_ids).count()
        total_rejected = base_queryset.filter(
            responses__user=user).exclude(selected_freelancer=user).count()
        total_selected = base_queryset.filter(selected_freelancer=user).count()
        total_active = base_queryset.filter(
            status='in_progress', selected_freelancer=user).count()
        total_completed = base_queryset.filter(
            status='completed', selected_freelancer=user).count()

        stats = {
            'total_applications': total_applied,
            'total_rejections': total_rejected,
            'total_selected': total_selected,
            'total_active': total_active,
            'total_completed': total_completed,
            'total_bookmarked': total_bookmarked,
        }

        if not status_filter or status_filter == 'applied':
            jobs = Job.objects.filter(responses__user=user).filter(
                filters).distinct().order_by(ordering)
            paginated = paginator.paginate_queryset(jobs, request)
            serializer = JobSearchSerializer(paginated, many=True, context={
                'bookmarked_ids': bookmarked_ids,
                'applied_ids': applied_ids
            })
            return paginator.get_paginated_response({
                'status': 'applied',
                'job_count': jobs.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter == 'rejected':
            jobs = Job.objects.filter(responses__user=user).exclude(
                selected_freelancer=user).filter(filters).distinct().order_by(ordering)
            paginated = paginator.paginate_queryset(jobs, request)
            serializer = JobSearchSerializer(paginated, many=True, context={
                'bookmarked_ids': bookmarked_ids,
                'applied_ids': applied_ids
            })
            return paginator.get_paginated_response({
                'status': 'rejected',
                'job_count': jobs.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter in ['in_progress', 'completed']:
            jobs = Job.objects.filter(selected_freelancer=user, status=status_filter).filter(
                filters).order_by(ordering)
            paginated = paginator.paginate_queryset(jobs, request)
            serializer = JobSearchSerializer(paginated, many=True, context={
                'bookmarked_ids': bookmarked_ids,
                'applied_ids': applied_ids
            })
            return paginator.get_paginated_response({
                'status': status_filter,
                'job_count': jobs.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter == 'selected':
            jobs = Job.objects.filter(selected_freelancer=user).filter(
                filters).order_by(ordering)
            paginated = paginator.paginate_queryset(jobs, request)
            serializer = JobSearchSerializer(paginated, many=True, context={
                'bookmarked_ids': bookmarked_ids,
                'applied_ids': applied_ids
            })
            return paginator.get_paginated_response({
                'status': 'selected',
                'job_count': jobs.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter == 'open':
            jobs = Job.objects.filter(status='open').filter(
                filters).order_by(ordering)
            paginated = paginator.paginate_queryset(jobs, request)
            serializer = JobSearchSerializer(paginated, many=True, context={
                'bookmarked_ids': bookmarked_ids,
                'applied_ids': applied_ids
            })
            return paginator.get_paginated_response({
                'status': 'open',
                'job_count': jobs.count(),
                'jobs': serializer.data,
                **stats
            })

        return DRFResponse({'detail': 'Invalid status filter.'}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Client Job Status Overview",
    description="""
            Get jobs posted by the authenticated client filtered by status.
            Supports filters and date ranges:
            - status: open, in_progress, completed, applied, selected, rejected
            - category filters
            - deadline and posted date filters
            Returns paginated job lists plus stats on applications, selections, and rejections.
            """,
    parameters=[
        OpenApiParameter(name='status', description="Job status filter", required=False,
                            type=str, enum=['open', 'in_progress', 'completed', 'applied', 'selected', 'rejected']),
        OpenApiParameter(
            name='category', description="Filter by category name", required=False, type=str),
        OpenApiParameter(
            name='category_slug', description="Filter by category slug", required=False, type=str),
        OpenApiParameter(name='deadline_before',
                            description="Filter jobs with deadline before this date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(name='deadline_after',
                            description="Filter jobs with deadline after this date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(
            name='posted_before', description="Filter jobs posted before this date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(
            name='posted_after', description="Filter jobs posted after this date (YYYY-MM-DD)", required=False, type=str),
        OpenApiParameter(
            name='ordering', description="Order jobs by fields", required=False, type=str),
        OpenApiParameter(
            name='page', description="Page number for pagination", required=False, type=int),
    ],
    responses={
        200: OpenApiResponse(description="Paginated client job list with status summary"),
        400: OpenApiResponse(description="Invalid status or filter parameters"),
        403: OpenApiResponse(description="Access denied for non-clients"),
    },
    tags=["Jobs", "Client"]
)
class ClientJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile

        if profile.user_type != 'client':
            return DRFResponse(
                {'detail': 'Only clients can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )

        status_filter = request.query_params.get('status')
        if status_filter == 'active':
            status_filter = 'in_progress'

        try:
            filters = get_job_filters(request)
        except ValueError as e:
            return DRFResponse({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ordering = request.query_params.get('ordering', '-posted_date')
        paginator = PageNumberPagination()
        paginator.page_size = 10

        jobs_qs = Job.objects.filter(client=profile).filter(
            filters).order_by(ordering)

        # Stats
        total_open = jobs_qs.filter(status='open').count()
        total_completed = jobs_qs.filter(status='completed').count()
        total_in_progress = jobs_qs.filter(status='in_progress').count()
        total_applications = JobResponse.objects.filter(
            job__client=profile).count()
        total_rejections = JobResponse.objects.filter(job__client=profile).exclude(
            user=F('job__selected_freelancer')).count()
        total_selected = JobResponse.objects.filter(
            job__client=profile, user=F('job__selected_freelancer')).count()

        stats = {
            'total_open': total_open,
            'total_completed': total_completed,
            'total_in_progress': total_in_progress,
            'total_applications': total_applications,
            'total_rejections': total_rejections,
            'total_selected': total_selected,
        }

        # No filter — return all
        if not status_filter:
            paginated = paginator.paginate_queryset(jobs_qs, request)
            serializer = JobSearchSerializer(paginated, many=True)
            return paginator.get_paginated_response({
                'status': 'all',
                'count': jobs_qs.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter in ['open', 'in_progress', 'completed']:
            filtered = jobs_qs.filter(status=status_filter)
            paginated = paginator.paginate_queryset(filtered, request)
            serializer = JobSearchSerializer(paginated, many=True)
            return paginator.get_paginated_response({
                'status': status_filter,
                'count': filtered.count(),
                'jobs': serializer.data,
                **stats
            })

        if status_filter == 'applied':
            jobs = jobs_qs.prefetch_related('responses__user__profile').annotate(
                application_count=Count('responses'))
            job_applications = []
            for job in jobs:
                responses = job.responses.all()
                serialized_responses = ResponseListSerializer(
                    responses, many=True).data
                job_applications.append({
                    'job_id': job.id,
                    'job_title': job.title,
                    'job_slug': job.slug,
                    'applications': serialized_responses,
                    'applications_count': job.application_count
                })
            paginated = paginator.paginate_queryset(job_applications, request)
            return paginator.get_paginated_response({
                'status': 'applied',
                'count': len(job_applications),
                'jobs': paginated,
                **stats
            })

        if status_filter == 'selected':
            responses = JobResponse.objects.filter(
                job__client=profile,
                user=F('job__selected_freelancer'),
                job__selected_freelancer__isnull=False
            ).select_related('job', 'user', 'user__profile')

            job_selections = {}
            for response in responses:
                job = response.job
                if job.id not in job_selections:
                    job_selections[job.id] = {
                        'job_id': job.id,
                        'job_title': job.title,
                        'job_slug': job.slug,
                        'selected_freelancer': []
                    }
                serialized = ResponseListSerializer(response).data
                job_selections[job.id]['selected_freelancer'].append(
                    serialized)

            selection_list = list(job_selections.values())
            paginated = paginator.paginate_queryset(selection_list, request)
            return paginator.get_paginated_response({
                'status': 'selected',
                'count': len(selection_list),
                'jobs': paginated,
                **stats
            })

        if status_filter == 'rejected':
            responses = JobResponse.objects.filter(
                job__client=profile
            ).exclude(user=F('job__selected_freelancer')).select_related('user', 'job', 'user__profile')

            job_rejections = {}
            for response in responses:
                job = response.job
                if job.id not in job_rejections:
                    job_rejections[job.id] = {
                        'job_id': job.id,
                        'job_title': job.title,
                        'job_slug': job.slug,
                        'rejected_applicants': []
                    }
                serialized = ResponseListSerializer(response).data
                job_rejections[job.id]['rejected_applicants'].append(
                    serialized)

            rejection_list = list(job_rejections.values())
            paginated = paginator.paginate_queryset(rejection_list, request)
            return paginator.get_paginated_response({
                'status': 'rejected',
                'count': len(rejection_list),
                'jobs': paginated,
                **stats
            })

        return DRFResponse({
            'detail': 'Invalid status filter. Use open, in_progress, completed, applied, selected, or rejected.'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Job Dashboard Summary",
    description="""
        Retrieve a summary dashboard for the authenticated user, showing job stats and wallet stats.
        Returns different data depending on user type (client or freelancer).
        """,
    responses={
        200: OpenApiResponse(description="Dashboard summary including job and wallet statistics"),
        400: OpenApiResponse(description="Missing user profile or user type"),
        500: OpenApiResponse(description="Failed to retrieve dashboard summary"),
    },
    tags=["Dashboard"]
)
class JobDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)

        try:
            if not profile or not profile.user_type:
                return DRFResponse({
                    'detail': 'User profile or user_type is missing.'
                }, status=status.HTTP_400_BAD_REQUEST)

            summary = {}
            job_stats = {}
            wallet_stats = get_wallet_stats(user)

            if profile.user_type == 'client':
                jobs = Job.objects.filter(client=profile)
                responses = JobResponse.objects.filter(job__client=profile)

                job_stats = {
                    'total_jobs': jobs.count(),
                    'open_jobs': jobs.filter(status='open').count(),
                    'in_progress_jobs': jobs.filter(status='in_progress').count(),
                    'completed_jobs': jobs.filter(status='completed').count(),
                    'total_responses': responses.count(),
                    'total_selected': responses.filter(user=F('job__selected_freelancer')).count(),
                    'total_rejections': responses.exclude(user=F('job__selected_freelancer')).count(),
                    'total_pending_responses': responses.filter(job__selected_freelancer__isnull=True).count()
                }

            elif profile.user_type == 'freelancer':
                applied_jobs = JobResponse.objects.filter(
                    user=user).values_list('job_id', flat=True)
                bookmarked_jobs = JobBookmark.objects.filter(
                    user=user).values_list('job_id', flat=True)

                job_stats = {
                    'applied_jobs': len(applied_jobs),
                    'rejected_jobs': Job.objects.filter(id__in=applied_jobs).exclude(selected_freelancer=user).count(),
                    'selected_jobs': Job.objects.filter(id__in=applied_jobs, selected_freelancer=user).count(),
                    'assigned_jobs': Job.objects.filter(selected_freelancer=user, status='in_progress').count(),
                    'completed_jobs': Job.objects.filter(selected_freelancer=user, status='completed').count(),
                    'bookmarked_jobs': len(bookmarked_jobs),
                }

            summary['job_stats'] = job_stats
            summary['wallet_stats'] = wallet_stats

            logger.info(f"{user.username} fetched dashboard summary.")

            return DRFResponse({
                'detail': 'Dashboard summary retrieved successfully.',
                'summary': summary
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
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='category',
                description='Filter jobs by category',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='preferred_freelancer_level',
                description='Filter jobs by preferred freelancer level',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='status_filter',
                description="Filter jobs by status filter: 'best_match', 'most_recent', 'trending', 'near_deadline', or 'open'",
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of jobs with pagination and bookmark/application info"),
            400: OpenApiResponse(description="Invalid status_filter"),
            403: OpenApiResponse(description="Authentication required for best_match filter"),
            500: OpenApiResponse(description="Unexpected server error"),
        },
        tags=['Job Discovery'],
        summary="Retrieve a paginated list of jobs with optional filters and status filters",
    )

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


@extend_schema_view(
    list=extend_schema(
        summary="List all chats for the authenticated user",
        responses={200: ChatSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Retrieve a specific chat",
        responses={200: ChatSerializer}
    ),
    create=extend_schema(
        summary="Create a new chat (only allowed by the job's client)",
        responses={
            201: ChatSerializer,
            400: OpenApiResponse(description="Job ID is required"),
            403: OpenApiResponse(description="Only the job's client can create a chat")
        }
    ),
    update=extend_schema(
        summary="Update a chat (permission required)",
        responses={
            200: ChatSerializer,
            403: OpenApiResponse(description="Permission denied"),
        }
    ),
    partial_update=extend_schema(
        summary="Partially update a chat",
        responses={
            200: ChatSerializer,
            403: OpenApiResponse(description="Permission denied"),
        }
    ),
    destroy=extend_schema(
        summary="Archive (delete) a chat (permission required)",
        responses={
            200: OpenApiResponse(description="Chat archived successfully"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
)
class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'profile', None)
        if not profile:
            logger.warning(f"User {user} has no profile.")
            return Chat.objects.none()
        return Chat.objects.filter(Q(client=profile) | Q(freelancer=profile))

    def perform_create(self, serializer):
        job = serializer.validated_data.get('job')
        if not job:
            logger.warning("Attempt to create chat without job.")
            return DRFResponse(
                {"message": "Job ID is required to create a chat."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if self.request.user.profile != job.client:
            logger.warning(
                f"Unauthorized chat creation by {self.request.user}.")
            return DRFResponse(
                {"message": "Only the job's client can create a chat."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(client=self.request.user.profile)

    def perform_update(self, serializer):
        chat = self.get_object()
        if not chat.can_access(self.request.user):
            logger.warning(f"Unauthorized chat update by {self.request.user}.")
            return DRFResponse(
                {"message": "You do not have permission to update this chat."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()

    def perform_destroy(self):
        chat = self.get_object()
        if not chat.can_access(self.request.user):
            logger.warning(f"Unauthorized chat delete by {self.request.user}.")
            return DRFResponse(
                {"message": "You do not have permission to delete this chat."},
                status=status.HTTP_403_FORBIDDEN
            )
        chat.archive()
        return DRFResponse(
            {"message": "Chat archived successfully."},
            status=status.HTTP_200_OK
        )


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'profile', None)
        if not profile:
            logger.warning(f"User {user} has no profile.")
            return Message.objects.none()

        chats = Chat.objects.filter(Q(client=profile) | Q(freelancer=profile))
        return Message.objects.filter(chat__in=chats, is_deleted=False)

    def get_chat(self, chat_uuid):
        try:
            chat = Chat.objects.get(chat_uuid=chat_uuid)
        except Chat.DoesNotExist:
            return None
        if not chat.can_access(self.request.user):
            return None
        return chat

    @extend_schema(
        summary="Send a message with optional attachments",
        description=(
            "Send a message in a chat with optional file attachments. "
            "Attachments can be multiple files (images, documents, etc.)."
        ),
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content of the message",
                    },
                    "attachments": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "binary",
                            "description": "File attachment (image, doc, etc.)"
                        },
                        "description": "Optional list of file attachments",
                    },
                },
                "required": ["content"],
            }
        },
        responses={
            201: OpenApiResponse(
                description="Message sent successfully.",
                response=MessageSerializer
            ),
            400: OpenApiResponse(description="Bad request, e.g. missing content or invalid files."),
            403: OpenApiResponse(description="Access denied to chat or forbidden action."),
        },
        tags=["Messages"],
    )

    def create(self, request, chat_uuid=None):
        chat = self.get_chat(chat_uuid)
        if not chat:
            return DRFResponse(
                {"message": "Chat not found or access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content = serializer.validated_data.get('content')
        if not content:
            return DRFResponse(
                {"message": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message = serializer.save(
            sender=request.user, chat=chat, is_read=False)

        # Handle attachments
        for file in request.FILES.getlist('attachments'):
            try:
                MessageAttachment.objects.create(
                    message=message,
                    file=file,
                    filename=file.name,
                    file_size=file.size,
                    content_type=file.content_type
                )
            except Exception as e:
                logger.error(f"Attachment error: {e}")
                return DRFResponse(
                    {"message": "Failed to process attachment."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Send notification
        recipient = chat.get_other_participant(request.user)
        if recipient:
            try:
                Notification.objects.create(
                    user=recipient,
                    message=f"{request.user.username} sent you a message in {chat.job.title}",
                    chat=chat
                )
            except Exception as e:
                logger.error(f"Notification error: {e}")

        return DRFResponse(self.get_serializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List messages by chat UUID",
        description="Retrieve all non-deleted messages for a given chat.",
        responses={
            200: OpenApiResponse(description="List of messages", response=MessageSerializer(many=True)),
            403: OpenApiResponse(description="Chat not found or access denied."),
        },
        tags=["Messages"],
    )
    def list_by_chat(self, request, chat_uuid=None):
        chat = self.get_chat(chat_uuid)
        if not chat:
            return DRFResponse(
                {"message": "Chat not found or access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        messages = Message.objects.filter(chat=chat, is_deleted=False)
        serializer = self.get_serializer(messages, many=True)
        return DRFResponse(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Retrieve a message by chat UUID and message ID",
        description="Get details of a specific message within a chat.",
        responses={
            200: OpenApiResponse(description="Message details", response=MessageSerializer),
            403: OpenApiResponse(description="Chat not found or access denied."),
            404: OpenApiResponse(description="Message not found."),
        },
        tags=["Messages"],
    )
    def retrieve_by_chat_uuid(self, request, chat_uuid=None, message_id=None):
        chat = self.get_chat(chat_uuid)
        if not chat:
            return DRFResponse(
                {"message": "Chat not found or access denied."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            message = Message.objects.get(
                chat=chat, id=message_id, is_deleted=False)
        except Message.DoesNotExist:
            return DRFResponse({"message": "Message not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(message)
        return DRFResponse(serializer.data)

    @extend_schema(
        summary="Update a message by chat UUID and message ID",
        description=(
            "Update message content if permitted. "
            "Partial update supported."
        ),
        request=MessageSerializer,
        responses={
            200: OpenApiResponse(description="Message updated successfully."),
            400: OpenApiResponse(description="Invalid data."),
            403: OpenApiResponse(description="Permission denied or cannot edit this message."),
            404: OpenApiResponse(description="Message not found."),
        },
        tags=["Messages"],
    )
    def update_by_chat_uuid(self, request, chat_uuid=None, message_id=None):
        chat = self.get_chat(chat_uuid)
        if not chat:
            return DRFResponse({"message": "Chat not found or access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            message = Message.objects.get(
                chat=chat, id=message_id, is_deleted=False)
        except Message.DoesNotExist:
            return DRFResponse({"message": "Message not found."}, status=status.HTTP_404_NOT_FOUND)

        if not message.can_edit(request.user):
            return DRFResponse(
                {"message": "You cannot edit this message. It may be too old or already deleted."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(
            message, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return DRFResponse({"message": "Message updated successfully."}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete (soft-delete) a message by chat UUID and message ID",
        description="Soft-delete a message if user has permission.",
        responses={
            200: OpenApiResponse(description="Message deleted successfully."),
            403: OpenApiResponse(description="Permission denied or cannot delete this message."),
            404: OpenApiResponse(description="Message not found."),
        },
        tags=["Messages"],
    )
    def destroy_by_chat_uuid(self, request, chat_uuid=None, message_id=None):
        chat = self.get_chat(chat_uuid)
        if not chat:
            return DRFResponse({"message": "Chat not found or access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            message = Message.objects.get(
                chat=chat, id=message_id, is_deleted=False)
        except Message.DoesNotExist:
            return DRFResponse({"message": "Message not found."}, status=status.HTTP_404_NOT_FOUND)

        if not message.can_delete(request.user):
            return DRFResponse(
                {"message": "You cannot delete this message. It may be too old or already deleted."},
                status=status.HTTP_403_FORBIDDEN
            )

        message.is_deleted = True
        message.save()
        return DRFResponse({"message": "Message deleted successfully."}, status=status.HTTP_200_OK)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List user notifications",
        responses={200: NotificationSerializer(many=True)},
        tags=["Notifications"],
    )
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Create notification (not allowed)",
        description="Manual creation of notifications is forbidden.",
        responses={403: OpenApiResponse(
            description="Notifications cannot be created manually.")},
        tags=["Notifications"],
    )
    def perform_create(self, serializer):
        logger.warning(
            f"User {self.request.user} tried to manually create a notification.")
        return DRFResponse(
            {"message": "Notifications cannot be created manually."},
            status=status.HTTP_403_FORBIDDEN
        )

    @extend_schema(
        summary="Update a notification",
        responses={
            200: OpenApiResponse(description="Notification updated successfully."),
            403: OpenApiResponse(description="Permission denied to update this notification."),
        },
        tags=["Notifications"],
    )
    def perform_update(self, serializer):
        notification = self.get_object()
        if notification.user != self.request.user:
            logger.warning(
                f"Unauthorized update attempt by {self.request.user}.")
            return DRFResponse(
                {"message": "You do not have permission to update this notification."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()
        return DRFResponse(
            {"message": "Notification updated successfully."},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Delete a notification",
        responses={
            200: OpenApiResponse(description="Notification deleted successfully."),
            403: OpenApiResponse(description="Permission denied to delete this notification."),
        },
        tags=["Notifications"],
    )
    def perform_destroy(self):
        notification = self.get_object()
        if notification.user != self.request.user:
            logger.warning(
                f"Unauthorized delete attempt by {self.request.user}.")
            return DRFResponse(
                {"message": "You do not have permission to delete this notification."},
                status=status.HTTP_403_FORBIDDEN
            )
        notification.delete()
        return DRFResponse(
            {"message": "Notification deleted successfully."},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Mark notification as read",
        description="Mark a notification as read for the authenticated user.",
        responses={
            200: OpenApiResponse(description="Notification marked as read."),
            403: OpenApiResponse(description="Permission denied to mark this notification."),
        },
        tags=["Notifications"],
    )
    @action(detail=True, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        if notification.user != self.request.user:
            logger.warning(
                f"Unauthorized mark-as-read by {self.request.user}.")
            return DRFResponse(
                {"message": "You do not have permission to mark this notification as read."},
                status=status.HTTP_403_FORBIDDEN
                )


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, CanReview]
    

    def get_queryset(self):
        recipient_id = self.request.query_params.get('recipient')
        if recipient_id:
            return Review.objects.filter(recipient_id=recipient_id)
        return Review.objects.all()

    @extend_schema(
        summary="List reviews",
        description="Retrieve a list of reviews. Optionally filter by recipient user ID using ?recipient= query parameter.",
        parameters=[
            OpenApiParameter(
                name='recipient',
                description='Filter reviews by recipient user ID',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={
            200: ReviewSerializer(many=True),
        },
        tags=["Reviews"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve a review",
        responses={
            200: ReviewSerializer,
            404: OpenApiResponse(description="Review not found"),
        },
        tags=["Reviews"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Create a review",
        request=ReviewSerializer,
        responses={
            201: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
        tags=["Reviews"],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Update a review",
        request=ReviewSerializer,
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        },
        tags=["Reviews"],
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Partial update a review",
        request=ReviewSerializer,
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        },
        tags=["Reviews"],
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a review",
        responses={
            204: OpenApiResponse(description="Review deleted successfully"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        },
        tags=["Reviews"],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        try:
            serializer.save(reviewer=self.request.user)
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error during review creation: {e}")
            raise serializers.ValidationError(
                {"detail": f"Database error while saving review: {str(e)}"})


class UserReviewSummaryView(APIView):
    permission_classes = [AllowAny]
    pagination_class = PageNumberPagination
    
    @extend_schema(
        summary="Get review summary for a user",
        description="Returns average rating, review count, recent reviews, all reviews (paginated), "
                    "and user stats including portfolio or client job stats depending on user type.",
        parameters=[
            OpenApiParameter(
                name="username",
                description="Username of the user to get review summary for",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Review summary and paginated reviews",
                response={
                    "type": "object",
                    "properties": {
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "username": {"type": "string"},
                                "user_type": {"type": "string"},
                                "profile_pic": {"type": ["string", "null"], "format": "uri"},
                            },
                        },
                        "average_rating": {"type": "number", "format": "float"},
                        "review_count": {"type": "integer"},
                        "recent_reviews": {"type": "array", "items": ReviewSerializer().data},
                        "all_reviews": {"type": "array", "items": ReviewSerializer().data},
                        "client_stats": {"type": "object", "nullable": True},
                        "portfolio": {"type": "object", "nullable": True},
                    },
                },
            ),
            404: OpenApiResponse(description="User or profile not found."),
        },
        tags=["Reviews"],
    )
    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile = getattr(user, 'profile', None)

        if not profile:
            return DRFResponse({'detail': 'User has no profile'}, status=status.HTTP_404_NOT_FOUND)

        user_type = profile.user_type
        average_rating = round(Review.average_rating_for(user), 2)
        review_count = Review.review_count_for(user)
        recent_reviews = Review.recent_reviews_for(user, limit=3)

        # Paginate all reviews
        all_reviews_qs = Review.reviews_for(user)
        paginator = self.pagination_class()
        paginated_reviews = paginator.paginate_queryset(
            all_reviews_qs, request)
        serialized_all_reviews = ReviewSerializer(
            paginated_reviews, many=True).data

        response_data = {
            "user": {
                "id": user.id,
                "username": user.username,
                "user_type": user_type,
                "profile_pic": profile.profile_pic.url if profile.profile_pic else None,
            },
            "average_rating": average_rating,
            "review_count": review_count,
            "recent_reviews": ReviewSerializer(recent_reviews, many=True).data,
            "all_reviews": serialized_all_reviews
        }
        
        if user_type == 'client':
            try:
                total_jobs = Job.objects.filter(client=profile)
                open_jobs = total_jobs.filter(status='open')
                paid_jobs = total_jobs.filter(payment_verified=True)
                selected_jobs = total_jobs.filter(selected_freelancer__isnull=False)

                response_data["client_stats"] = {
                    "total_jobs_posted": total_jobs.count(),
                    "currently_open_jobs": open_jobs.count(),
                    "total_selected_freelancers": selected_jobs.count(),
                    "total_amount_spent": float(paid_jobs.aggregate(
                        total=Sum('price'))['total'] or 0.0)
                }
            except Exception as e:
                response_data["client_stats"] = {
                    "error": f"Failed to calculate stats: {str(e)}"
                }

        # Attach freelancer portfolio if applicable
        if user_type == 'freelancer':
            try:
                freelancer_profile = user.profile.freelancer_profile
                response_data["portfolio"] = {
                    "hourly_rate": freelancer_profile.hourly_rate,
                    "availability": freelancer_profile.availability,
                    "experience_years": freelancer_profile.experience_years,
                    "portfolio_link": freelancer_profile.portfolio_link,
                    "skills": [s.name for s in freelancer_profile.skills.all()],
                    "languages": [l.name for l in freelancer_profile.languages.all()],
                }
            except FreelancerProfile.DoesNotExist:
                response_data["portfolio"] = {}
                

        return paginator.get_paginated_response(response_data)
