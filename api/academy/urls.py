from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import TrainingViewSet

router = DefaultRouter()
router.register(r'trainings', TrainingViewSet, basename='training')

urlpatterns = [
    path('', include(router.urls)),
]
