# Generated by Django 5.0.1 on 2024-08-25 07:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0017_mealplan_has_changes_mealplan_is_approved_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meal',
            name='dietary_preference',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]