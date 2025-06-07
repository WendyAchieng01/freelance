from .views import MessageViewSet
from django.urls import path, include
from django.urls import path
from .views import ChatViewSet, MessageViewSet, MessageAttachmentViewSet

chat_message_list_and_create = MessageViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

chat_list = ChatViewSet.as_view({
    'get': 'list',
})

message_crud = MessageViewSet.as_view({
    'retrieve': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('chats/', chat_list, name='list-chats'),
    path('chats/<slug:chat_slug>/message/', chat_message_list_and_create, name='chat-message-list-create'),
    path('chats/<slug:chat_slug>/message/<int:pk>/', message_crud, name='chat-messages-detail'),

]