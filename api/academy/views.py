from rest_framework import viewsets,filters,permissions,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from academy.models import Training
from core.models import Job
from .serializers import TrainingSerializer
from .permissions import IsClientAndOwnerOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser


from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TrainingViewSet(viewsets.ModelViewSet):
    serializer_class = TrainingSerializer
    permission_classes = [IsAuthenticated, IsClientAndOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'texts']
    ordering_fields = ['title', 'slug']
    ordering = ['slug']
    lookup_field = 'slug'
    pagination_class = StandardResultsSetPagination
    
    
    
    

    def get_queryset(self):
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

    def perform_create(self, serializer):
        job_slug = self.kwargs.get('job_slug')
        job = get_object_or_404(Job, slug=job_slug, client=self.request.user)
        serializer.save(client=self.request.user, job=job)
