from django.urls import re_path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, MessageViewSet, NotificationViewSet

# Use ReadOnlyModelViewSet for notifications and chats
chat_list_view = ChatViewSet.as_view({
    'get': 'list',
})

notification_list_view = NotificationViewSet.as_view({
    'get': 'list',
})

notification_detail_view = NotificationViewSet.as_view({
    'get': 'retrieve',
})

# Message views (full CRUD)
message_list_create = MessageViewSet.as_view({
    'get': 'list_by_chat',
    'post': 'create',
})

message_detail = MessageViewSet.as_view({
    'get': 'retrieve_by_chat_uuid',
    'put': 'update_by_chat_uuid',
    'delete': 'destroy_by_chat_uuid',
})

urlpatterns = [
    # 🔹 Chat endpoints
    re_path(r'^chats/$', chat_list_view, name='chat-list'),

    # 🔹 Message endpoints
    re_path(r'^chats/(?P<chat_uuid>[0-9a-f-]+)/$', message_list_create, name='message-list-by-chat'),
    re_path(r'^chats/(?P<chat_uuid>[0-9a-f-]+)/(?P<message_id>\d+)/$', message_detail, name='message-detail-by-uuid'),

    # 🔹 Notification endpoints (read-only)
    re_path(r'^notifications/$', notification_list_view, name='notification-list'),
    re_path(r'^notifications/(?P<pk>\d+)/$', notification_detail_view, name='notification-detail'),
]
