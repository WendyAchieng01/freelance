# Generated by Django 5.1.2 on 2025-06-02 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='training',
            name='slug',
            field=models.SlugField(blank=True, null=True, unique=True),
        ),
    ]
