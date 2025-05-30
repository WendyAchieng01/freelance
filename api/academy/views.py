from rest_framework import viewsets,filters,permissions,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from academy.models import Training
from core.models import Job
from .serializers import TrainingSerializer
from .permissions import IsClientAndOwnerOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser


class TrainingViewSet(viewsets.ModelViewSet):
    serializer_class = TrainingSerializer
    permission_classes = [IsAuthenticated, IsClientAndOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'texts', 'slug']
    ordering_fields = ['title', 'id']
    ordering = ['id']

    def get_queryset(self):
        user = self.request.user

        if 'slug' in self.kwargs:
            return Training.objects.filter(slug=self.kwargs['slug'])

        job_slug = self.kwargs.get('job_slug')
        qs = Training.objects.all()

        if job_slug:
            qs = qs.filter(job__slug=job_slug)

        if user.profile.user_type == 'client':
            return qs.filter(client=user)
        elif user.profile.user_type == 'freelancer':
            return qs  # freelancers can view all trainings
        return qs.none()

    def get_object(self):
        if 'slug' in self.kwargs:
            return get_object_or_404(Training, slug=self.kwargs['slug'])
        return super().get_object()

    def perform_create(self, serializer):
        job_slug = self.kwargs.get('job_slug')
        job = get_object_or_404(
            Job, slug=job_slug, client=self.request.user.profile)
        serializer.save(client=self.request.user, job=job)
