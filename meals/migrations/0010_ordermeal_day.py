# Generated by Django 4.2 on 2023-12-26 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0009_ingredient_calories'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordermeal',
            name='day',
            field=models.CharField(choices=[('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'), ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday'), ('Sunday', 'Sunday')], default='Monday', max_length=10),
            preserve_default=False,
        ),
    ]