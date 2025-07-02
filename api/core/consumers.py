# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from core.models import Chat, Message, Notification
from .serializers import MessageSerializer, NotificationSerializer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.chat_group_name = f'chat_{self.chat_id}'
        user = self.scope['user']

        chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)
        if not chat.can_access(user):
            await self.close()
            return

        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data['message']
        user = self.scope['user']
        chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)

        if chat.can_access(user):
            new_message = await database_sync_to_async(Message.objects.create)(
                chat=chat,
                sender=user,
                content=message_content
            )
            serializer = await database_sync_to_async(MessageSerializer)(new_message)

            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    'type': 'chat_message',
                    'message': serializer.data
                }
            )

            recipient = await database_sync_to_async(chat.get_other_participant)(user)
            if recipient:
                notification = await database_sync_to_async(Notification.objects.create)(
                    user=recipient,
                    message=f"{user.username} sent you a message in {chat.job.title}",
                    chat=chat
                )
                notification_data = await database_sync_to_async(NotificationSerializer)(notification)
                await self.channel_layer.group_send(
                    f'notifications_{recipient.id}',
                    {
                        'type': 'notification_message',
                        'notification': notification_data.data
                    }
                )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'message': event['message']}))


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.notification_group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(self.notification_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.notification_group_name, self.channel_name)

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({'notification': event['notification']}))
