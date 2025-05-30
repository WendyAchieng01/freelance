from django.urls import path
from .views import ChatViewSet, MessageViewSet, MessageAttachmentViewSet

chat_list = ChatViewSet.as_view({'get': 'list', 'post': 'create'})
chat_detail = ChatViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})

message_list = MessageViewSet.as_view({'get': 'list', 'post': 'create'})
message_detail = MessageViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})

attachment_list = MessageAttachmentViewSet.as_view(
    {'get': 'list', 'post': 'create'})
attachment_detail = MessageAttachmentViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})
attachment_download = MessageAttachmentViewSet.as_view({'get': 'download'})

urlpatterns = [
    path('list/', chat_list),
    path('detail/<int:pk>/', chat_detail),

    path('list/', message_list),
    path('detail/<int:pk>/', message_detail),

    path('list/', attachment_list),
    path('detail/<int:pk>/', attachment_detail),
    path('attachment/<int:pk>/download/', attachment_download),
]
