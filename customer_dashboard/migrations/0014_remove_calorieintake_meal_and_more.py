# Generated by Django 4.2 on 2024-01-14 19:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0013_calorieintake'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='calorieintake',
            name='meal',
        ),
        migrations.AddField(
            model_name='calorieintake',
            name='meal_description',
            field=models.TextField(blank=True, null=True),
        ),
    ]
