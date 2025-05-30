# trainings/urls.py

from django.urls import path
from .views import TrainingViewSet

training_list_create = TrainingViewSet.as_view(
    {'get': 'list', 'post': 'create'})
training_detail = TrainingViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

urlpatterns = [
    # Scoped by job
    path('<slug:job_slug>/', training_list_create, name='training-list-create'),

    # Global detail by training slug
    path('detail/<slug:slug>/', training_detail, name='training-detail'),
]
