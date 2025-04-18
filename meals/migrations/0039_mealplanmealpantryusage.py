# Generated by Django 4.2.10 on 2025-01-03 05:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0038_pantryitem_used_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='MealPlanMealPantryUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_used', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('meal_plan_meal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pantry_usage', to='meals.mealplanmeal')),
                ('pantry_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='meals.pantryitem')),
            ],
        ),
    ]
