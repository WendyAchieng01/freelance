from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Message
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@receiver(post_save, sender=Message)
def notify_unread_messages(sender, instance, created, **kwargs):
    if not created:
        return

    # Determine recipient
    chat = instance.chat
    recipient = chat.freelancer.user if instance.sender != chat.freelancer.user else chat.client.user

    # Broadcast to recipient's WebSocket channel group
    channel_layer = get_channel_layer()
    group_name = f"user_{recipient.id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "unread.message",
            "chat_slug": chat.slug,
            "unread_count": chat.messages.filter(is_read=False).exclude(sender=recipient).count()
        }
    )


@receiver(post_save, sender=Message)
def send_message_notification(sender, instance, created, **kwargs):
    if not created:
        return

    chat = instance.chat
    channel_layer = get_channel_layer()

    # Broadcast to chat participants
    async_to_sync(channel_layer.group_send)(
        f'chat_{chat.slug}',
        {
            'type': 'new_message',
            'message': instance.content,
            'sender': instance.sender.username,
            'timestamp': str(instance.timestamp)
        }
    )

    # Notify recipient’s unread count
    recipient = chat.client.user if instance.sender != chat.client.user else chat.freelancer.user
    unread_count = chat.messages.filter(
        is_read=False).exclude(sender=recipient).count()

    async_to_sync(channel_layer.group_send)(
        f'user_{recipient.id}',
        {
            'type': 'unread_message',
            'chat_slug': chat.slug,
            'unread_count': unread_count
        }
    )
