# Generated by Django 5.0.1 on 2024-03-12 05:39

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0006_chef_chef_embedding'),
        ('meals', '0014_alter_meal_unique_together_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='meal',
            constraint=models.UniqueConstraint(condition=models.Q(('chef__isnull', False)), fields=('chef', 'start_date'), name='unique_chef_meal_per_date'),
        ),
    ]
