from django.urls import re_path
from api.core.consumers import ChatConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>\d+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]
