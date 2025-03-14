# Generated by Django 5.1.2 on 2025-02-20 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_remove_profile_device_used_clientprofile_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Skill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='clientprofile',
            name='preferred_freelancer_level',
            field=models.CharField(choices=[('entry', 'Entry Level'), ('intermediate', 'Intermediate'), ('expert', 'Expert')], default='intermediate', max_length=50),
        ),
        migrations.AddField(
            model_name='clientprofile',
            name='project_budget',
            field=models.DecimalField(decimal_places=2, default=500.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='freelancerprofile',
            name='experience_years',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='freelancerprofile',
            name='hourly_rate',
            field=models.DecimalField(decimal_places=2, default=10.0, max_digits=10),
        ),
        migrations.RemoveField(
            model_name='freelancerprofile',
            name='skills',
        ),
        migrations.AddField(
            model_name='clientprofile',
            name='languages',
            field=models.ManyToManyField(blank=True, to='accounts.language'),
        ),
        migrations.AddField(
            model_name='freelancerprofile',
            name='languages',
            field=models.ManyToManyField(blank=True, to='accounts.language'),
        ),
        migrations.AddField(
            model_name='freelancerprofile',
            name='skills',
            field=models.ManyToManyField(blank=True, to='accounts.skill'),
        ),
    ]
