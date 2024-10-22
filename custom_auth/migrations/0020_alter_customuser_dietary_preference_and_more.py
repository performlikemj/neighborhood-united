# Generated by Django 4.2.10 on 2024-08-04 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0019_customuser_custom_allergies_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='dietary_preference',
            field=models.CharField(blank=True, choices=[('Vegan', 'Vegan'), ('Vegetarian', 'Vegetarian'), ('Pescatarian', 'Pescatarian'), ('Gluten-Free', 'Gluten-Free'), ('Keto', 'Keto'), ('Paleo', 'Paleo'), ('Halal', 'Halal'), ('Kosher', 'Kosher'), ('Low-Calorie', 'Low-Calorie'), ('Low-Sodium', 'Low-Sodium'), ('High-Protein', 'High-Protein'), ('Dairy-Free', 'Dairy-Free'), ('Nut-Free', 'Nut-Free'), ('Raw Food', 'Raw Food'), ('Whole 30', 'Whole 30'), ('Low-FODMAP', 'Low-FODMAP'), ('Diabetic-Friendly', 'Diabetic-Friendly'), ('Everything', 'Everything')], default='Everything', max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]