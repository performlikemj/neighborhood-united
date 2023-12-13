# Generated by Django 4.2 on 2023-12-07 14:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0005_customuser_dietary_preference'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='preferences',
        ),
        migrations.AlterField(
            model_name='address',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]