# Generated by Django 4.2.10 on 2025-01-03 04:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0037_pantryitem_marked_as_used'),
    ]

    operations = [
        migrations.AddField(
            model_name='pantryitem',
            name='used_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
