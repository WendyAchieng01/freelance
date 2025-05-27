from .views import FreelancerRecommendationsView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'jobs', views.JobViewSet, basename='job')
router.register(r'responses', views.ResponseViewSet, basename='response')
router.register(r'chats', views.ChatViewSet, basename='chat')
router.register(r'messages', views.MessageViewSet, basename='message')
router.register(r'attachments', views.MessageAttachmentViewSet, basename='attachment')
router.register(r'reviews', views.ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
    path('recommendations/', FreelancerRecommendationsView.as_view({'get': 'list'}), name='recommendations'),
]
