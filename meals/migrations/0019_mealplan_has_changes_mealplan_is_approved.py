# Generated by Django 4.2.10 on 2024-08-04 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0018_alter_mealplanmeal_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mealplan',
            name='has_changes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='mealplan',
            name='is_approved',
            field=models.BooleanField(default=False),
        ),
    ]
