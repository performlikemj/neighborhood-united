# Generated by Django 4.2 on 2023-11-20 05:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0004_alter_chef_profile_pic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chef',
            name='profile_pic',
            field=models.ImageField(blank=True, upload_to='chefs/profile_pics/'),
        ),
    ]
