# Generated by Django 4.2.10 on 2024-12-20 01:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0035_tag_alter_pantryitem_unique_together_and_more'),
        ('reviews', '0003_remove_review_not_both_meal_and_mealplan_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='meal',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='meals.meal'),
        ),
        migrations.AddField(
            model_name='review',
            name='meal_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='meals.mealplan'),
        ),
    ]
