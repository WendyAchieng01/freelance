# Generated by Django 5.0.3 on 2024-03-24 09:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_remove_profile_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='id_card',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name='profile',
            name='pay_id',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
