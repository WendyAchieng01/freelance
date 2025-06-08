from django.db import migrations
import uuid

def populate_chat_fields(apps, schema_editor):
    Chat = apps.get_model('core', 'Chat')
    for chat in Chat.objects.all():
        if not chat.chat_uuid:
            chat.chat_uuid = uuid.uuid4()
        if not chat.active:
            chat.active = False
        chat.save()

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_fix_chat_schema'),
    ]

    operations = [
        migrations.RunPython(populate_chat_fields),
    ]