# Generated by Django 4.2 on 2023-11-12 06:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0003_remove_chef_primary_postal_code_and_more'),
        ('meals', '0002_alter_mealplan_order'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='meal',
            unique_together={('chef', 'start_date', 'end_date')},
        ),
    ]