from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import TrainingViewSet

router = DefaultRouter()
router.register(r'trainings', TrainingViewSet, basename='training')



urlpatterns = [
    path('trainings/', TrainingViewSet.as_view({'get': 'list', 'post': 'create'}), name='training-list'),
    path('trainings/<slug:slug>/', TrainingViewSet.as_view(
        {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='training-detail'),
]
