# Generated by Django 5.1.2 on 2025-07-04 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_jobcategory_alter_job_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='required_freelancers',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='jobcategory',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
