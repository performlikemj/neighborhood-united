# Generated by Django 4.2.10 on 2024-12-20 11:13

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0027_remove_customuser_family_size_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='custom_allergies_array',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), blank=True, default=list, size=None),
        ),
    ]
