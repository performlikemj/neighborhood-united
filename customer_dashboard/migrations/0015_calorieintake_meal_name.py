# Generated by Django 4.2 on 2024-01-14 21:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0014_remove_calorieintake_meal_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='calorieintake',
            name='meal_name',
            field=models.TextField(blank=True, null=True),
        ),
    ]