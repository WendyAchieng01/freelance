from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, MessageViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'chats', ChatViewSet, basename='chat')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Router-generated URLs for chats and notifications
    path('', include(router.urls)),

    # Message endpoints using chat_uuid
    re_path( r'chats/(?P<chat_uuid>[0-9a-f-]+)/$',
        MessageViewSet.as_view({'get': 'list_by_chat', 'post': 'create'}), name='message-list-by-chat'
    ),
    path( 'chats/<int:pk>/', MessageViewSet.as_view(
            {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='message-detail'
    ),
]
