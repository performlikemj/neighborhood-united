# Generated by Django 4.2 on 2023-11-20 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0003_alter_meal_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='meal',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='meals/'),
        ),
    ]
