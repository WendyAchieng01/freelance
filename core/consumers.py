import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Chat, Message, MessageAttachment

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user_id = self.scope["user"].id
        
        # Save message to database
        saved_message = await self.save_message(user_id, message)
        
        # Get attachment data if available
        attachments = await self.get_message_attachments(saved_message.id)
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user_id': user_id,
                'username': self.scope["user"].username,
                'attachments': attachments
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'user_id': event['user_id'],
            'username': event['username'],
            'attachments': event.get('attachments', [])
        }))

    @database_sync_to_async
    def save_message(self, user_id, message):
        chat = Chat.objects.get(id=self.chat_id)
        return Message.objects.create(
            chat=chat,
            sender_id=user_id,
            content=message
        )

    @database_sync_to_async
    def get_message_attachments(self, message_id):
        message = Message.objects.get(id=message_id)
        attachments = []
        
        for attachment in message.attachments.all():
            attachments.append({
                'id': attachment.id,
                'filename': attachment.filename,
                'url': f'/attachment/{attachment.id}/download/',
                'file_size': attachment.file_size
            })
        
        return attachments
