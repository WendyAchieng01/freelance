from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from core.models import Chat, Message,MessageAttachment
import base64
import uuid


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.chat_slug = self.scope['url_route']['kwargs']['slug']
        self.user = self.scope["user"]

        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        self.chat = await self.get_chat(self.chat_slug)
        if not self.chat or not await self.is_participant(self.chat, self.user):
            await self.close()
            return

        self.group_name = f'chat_{self.chat_slug}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send last 50 messages on connect
        messages = await self.get_last_messages(self.chat, 50)
        await self.send_json({
            "type": "history",
            "messages": messages
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        action = content.get("type", "message")

        if action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "user_typing",
                    "sender": self.user.username
                }
            )
        elif action == "message":
            message_text = content.get("content", "").strip()
            attachments = content.get("attachments", [])

            if not message_text and not attachments:
                await self.send_json({'error': 'Message content or attachment required.'})
                return

            # Save message
            message = await self.save_message(self.chat, self.user, message_text)

            # Save attachments
            attachment_urls = []
            for file_data in attachments:
                file_url = await self.save_attachment(file_data, message)
                if file_url:
                    attachment_urls.append(file_url)

            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat_message',
                    'message_id': message.id,
                    'sender': self.user.username,
                    'content': message.content,
                    'timestamp': str(message.timestamp),
                    'attachments': attachment_urls
                }
            )

    async def chat_message(self, event):
        await self.send_json({
            "type": "new_message",
            "message_id": event["message_id"],
            "sender": event["sender"],
            "content": event["content"],
            "timestamp": event["timestamp"],
            "attachments": event["attachments"]
        })

    async def user_typing(self, event):
        await self.send_json({
            "type": "typing",
            "sender": event["sender"]
        })

    # Helpers (DB/Storage)

    @database_sync_to_async
    def get_chat(self, slug):
        try:
            return Chat.objects.select_related("client", "freelancer").get(slug=slug, active=True)
        except Chat.DoesNotExist:
            return None

    @database_sync_to_async
    def is_participant(self, chat, user):
        return chat.client.user == user or chat.freelancer.user == user

    @database_sync_to_async
    def save_message(self, chat, user, content):
        return Message.objects.create(chat=chat, sender=user, content=content)

    @database_sync_to_async
    def get_last_messages(self, chat, limit=50):
        return [
            {
                "message_id": msg.id,
                "sender": msg.sender.username,
                "content": msg.content,
                "timestamp": str(msg.timestamp),
                "attachments": [att.file.url for att in msg.attachments.all()]
            }
            for msg in Message.objects.filter(chat=chat).order_by("-timestamp")[:limit][::-1]
        ]

    @database_sync_to_async
    def save_attachment(self, base64_data, message):
        try:
            file_format, encoded = base64_data.split(';base64,')
            ext = file_format.split('/')[-1]
            file_name = f"{uuid.uuid4()}.{ext}"
            file_content = base64.b64decode(encoded)

            from django.core.files.base import ContentFile
            file = ContentFile(file_content, name=file_name)

            attachment = MessageAttachment.objects.create(
                message=message, file=file)
            return attachment.file.url
        except Exception:
            return None


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if user.is_anonymous:
            await self.close()
        else:
            self.group_name = f'user_{user.id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def unread_message(self, event):
        await self.send_json({
            'type': 'unread',
            'chat': event['chat_slug'],
            'unread_count': event['unread_count']
        })
