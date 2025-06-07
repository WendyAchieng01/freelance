import uuid
from django.db import migrations, models


def generate_unique_uuids(apps, schema_editor):
    Chat = apps.get_model('core', 'Chat')
    for chat in Chat.objects.all():
        chat.chat_uuid = uuid.uuid4()
        chat.save(update_fields=['chat_uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_chat_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='chat',
            name='chat_uuid',
            field=models.UUIDField(editable=False, null=True, unique=True),
        ),
        migrations.RunPython(generate_unique_uuids),
        migrations.AlterField(
            model_name='chat',
            name='chat_uuid',
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.DeleteModel(
            name='JobAssignment',
        ),
    ]
