# Generated by Django 4.2.10 on 2024-12-29 18:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0036_remove_meal_servings'),
    ]

    operations = [
        migrations.AddField(
            model_name='pantryitem',
            name='marked_as_used',
            field=models.BooleanField(default=False),
        ),
    ]
