# Generated by Django 4.2 on 2023-12-26 08:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0010_ordermeal_day'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ordermeal',
            name='day',
        ),
        migrations.AddField(
            model_name='ordermeal',
            name='meal_plan_meal',
            field=models.ForeignKey(default=10, on_delete=django.db.models.deletion.CASCADE, to='meals.mealplanmeal'),
            preserve_default=False,
        ),
    ]