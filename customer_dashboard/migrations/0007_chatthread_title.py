# Generated by Django 4.2 on 2023-11-23 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0006_remove_chatthread_title_delete_chatlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatthread',
            name='title',
            field=models.CharField(default='Chat with Assistant', max_length=255),
        ),
    ]
