# Generated by Django 4.2 on 2023-11-07 11:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mealplan',
            name='order',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='associated_meal_plan', to='meals.order'),
        ),
    ]