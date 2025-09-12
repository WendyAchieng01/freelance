from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0002_chat_active_chat_chat_uuid_chat_slug_job_slug_and_more'),
    ]

    operations = [
        
        # Add chat_uuid field
        migrations.AddField(
            model_name='Chat',
            name='chat_uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
            preserve_default=True,
        ),
        # Make freelancer nullable
        migrations.AlterField(
            model_name='Chat',
            name='freelancer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.DO_NOTHING,
                related_name='freelancer_chats',
                to='accounts.profile',
            ),
        ),
        # Add unique_together constraint
        migrations.AlterUniqueTogether(
            name='Chat',
            unique_together={('job', 'client', 'freelancer')},
        ),
    ]