# Generated by Django 5.1.2 on 2025-01-04 13:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('core', '0005_chatroom_chatmessage_delete_chat'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='chatroom',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='chatroom',
            name='client',
        ),
        migrations.RemoveField(
            model_name='chatroom',
            name='freelancer',
        ),
        migrations.RemoveField(
            model_name='chatroom',
            name='job',
        ),
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_chats', to='accounts.profile')),
                ('freelancer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='freelancer_chats', to='accounts.profile')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chats', to='core.job')),
            ],
        ),
        migrations.DeleteModel(
            name='ChatMessage',
        ),
        migrations.DeleteModel(
            name='ChatRoom',
        ),
    ]