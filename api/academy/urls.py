from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import TrainingViewSet

# Manual URL patterns for clarity
urlpatterns = [
    # List and create trainings for a specific job
    path(
        'trainings/<job_slug>/',
        TrainingViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='training-list'
    ),
    # Retrieve, update, and delete a specific training
    path(
        'trainings/<job_slug>/<slug>/',
        TrainingViewSet.as_view(
            {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}),
        name='training-detail'
    ),
]
