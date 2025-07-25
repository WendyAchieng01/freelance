# Generated by Django 5.1.2 on 2025-07-18 11:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_job_reviewed_responses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='response',
            name='status',
            field=models.CharField(blank=True, choices=[('submitted', 'Submitted'), ('under_review', 'Under Review'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='submitted', max_length=20, null=True),
        ),
    ]
