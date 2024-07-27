# Generated by Django 4.2.10 on 2024-07-27 06:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0018_customuser_timezone'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='custom_allergies',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='custom_dietary_preference',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
