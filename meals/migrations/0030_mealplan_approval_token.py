# Generated by Django 4.2.10 on 2024-10-23 03:09

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0029_pantryitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='mealplan',
            name='approval_token',
            field=models.UUIDField(blank=True, default=uuid.uuid4, null=True),
        ),
    ]
