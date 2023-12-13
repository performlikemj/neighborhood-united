# Generated by Django 4.2 on 2023-12-07 06:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0006_alter_meal_managers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meal',
            name='dietary_preference',
            field=models.CharField(blank=True, choices=[('Vegan', 'Vegan'), ('Vegetarian', 'Vegetarian'), ('Pescatarian', 'Pescatarian'), ('Gluten-Free', 'Gluten-Free'), ('Keto', 'Keto'), ('Paleo', 'Paleo'), ('Halal', 'Halal'), ('Kosher', 'Kosher'), ('Low-Calorie', 'Low-Calorie'), ('Low-Sodium', 'Low-Sodium'), ('High-Protein', 'High-Protein'), ('Dairy-Free', 'Dairy-Free'), ('Nut-Free', 'Nut-Free'), ('Raw Food', 'Raw Food'), ('Whole 30', 'Whole 30'), ('Low-FODMAP', 'Low-FODMAP'), ('Diabetic-Friendly', 'Diabetic-Friendly'), ('Everything', 'Everything')], max_length=20, null=True),
        ),
    ]
