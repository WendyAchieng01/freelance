from django.urls import path
from .views import ChatViewSet, MessageViewSet, MessageAttachmentViewSet

# Chat view actions
chat_list = ChatViewSet.as_view({'get': 'list', 'post': 'create'})
chat_detail = ChatViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})

# Message view actions
message_list = MessageViewSet.as_view({'get': 'list', 'post': 'create'})
message_detail = MessageViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})

# Attachment view actions
attachment_list = MessageAttachmentViewSet.as_view({'get': 'list', 'post': 'create'})
attachment_detail = MessageAttachmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})
attachment_download = MessageAttachmentViewSet.as_view({'get': 'download'})

urlpatterns = [
    # Chat routes
    path('chats/', chat_list, name='chat-list'),
    path('chats/<int:pk>/', chat_detail, name='chat-detail'),

    # Message routes
    path('', message_list, name='message-list'),
    path('<int:pk>/', message_detail, name='message-detail'),

    # Attachment routes
    path('attachments/', attachment_list, name='attachment-list'),
    path('attachments/<int:pk>/', attachment_detail, name='attachment-detail'),
    path('attachments/<int:pk>/download/', attachment_download, name='attachment-download'),
]
