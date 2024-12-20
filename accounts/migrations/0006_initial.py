# Generated by Django 5.0.3 on 2024-03-24 08:05

import django.contrib.auth.models
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0005_remove_freelancer_user_remove_profile_user_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_modified', models.DateTimeField(auto_now=True, verbose_name=django.contrib.auth.models.User)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('location', models.CharField(blank=True, max_length=200)),
                ('bio', models.TextField()),
                ('device_used', models.CharField(max_length=50)),
                ('profile_pic', models.ImageField(upload_to='profile_pic/')),
                ('pay_id', models.CharField(max_length=20)),
                ('id_card', models.IntegerField(validators=[django.core.validators.MaxValueValidator(99999999)])),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
