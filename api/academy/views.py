from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets, permissions, status, filters,status
from rest_framework.exceptions import PermissionDenied, APIException
from rest_framework.response import Response
from .permissions import IsClientAndOwnerOrReadOnly
from rest_framework.pagination import PageNumberPagination
from .serializers import TrainingSerializer


from academy.models import Training
from core.models import Job


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 100


class TrainingViewSet(viewsets.ModelViewSet):
    serializer_class = TrainingSerializer
    permission_classes = [
        permissions.IsAuthenticated, IsClientAndOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'texts']
    ordering_fields = ['title', 'slug']
    ordering = ['slug']
    lookup_field = 'slug'
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        try:
            user = self.request.user
            qs = Training.objects.all()
            job_slug = self.kwargs.get('job_slug')
            if job_slug:
                qs = qs.filter(job__slug=job_slug)
            if user.profile.user_type == 'client':
                return qs.filter(client=user)
            elif user.profile.user_type == 'freelancer':
                return qs
            return qs.none()
        except Exception:
            raise APIException(
                detail="Unable to retrieve trainings.", code=status.HTTP_400_BAD_REQUEST)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['job_slug'] = self.kwargs.get('job_slug')
        return context

    def get_object(self):
        try:
            slug = self.kwargs.get('slug')
            if not slug:
                raise APIException(
                    detail="Training slug is required.", code=status.HTTP_400_BAD_REQUEST)
            obj = get_object_or_404(Training, slug=slug)
            self.check_object_permissions(self.request, obj)
            return obj
        except PermissionDenied:
            raise
        except Exception:
            raise APIException(
                detail="Unable to access the training.", code=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        try:
            job_slug = self.kwargs.get('job_slug')
            if not job_slug:
                raise APIException(detail="Job slug is required.",
                                   code=status.HTTP_400_BAD_REQUEST)
            job = get_object_or_404(Job, slug=job_slug)
            if job.client != self.request.user.profile:
                raise PermissionDenied(
                    "You can only create trainings for your own jobs.")
            serializer.save(client=self.request.user, job=job)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PermissionDenied:
            raise
        except Exception:
            raise APIException(detail="Failed to create training.",
                               code=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        try:
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PermissionDenied:
            raise
        except Exception:
            raise APIException(detail="Failed to update training.",
                               code=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        try:
            instance.delete()
            return Response({"detail": "Training deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except PermissionDenied:
            raise
        except Exception:
            raise APIException(detail="Failed to delete training.",
                               code=status.HTTP_400_BAD_REQUEST)
