# Generated by Django 4.2 on 2023-11-16 05:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='week_shift',
            field=models.IntegerField(default=0),
        ),
    ]