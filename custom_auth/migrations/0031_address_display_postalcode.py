# Generated by Django 4.2.10 on 2025-03-15 20:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0030_rename_custom_allergies_array_customuser_custom_allergies'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='display_postalcode',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
    ]
