# Generated by Django 4.2.10 on 2025-05-17 05:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0033_customuser_email_token_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='email_token',
            field=models.UUIDField(db_index=True, editable=False, unique=True),
        ),
    ]
