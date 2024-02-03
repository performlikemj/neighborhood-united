# Generated by Django 4.2 on 2024-02-02 20:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0015_calorieintake_meal_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='calorieintake',
            name='portion_size',
            field=models.CharField(choices=[('XS', 'Extra Small'), ('S', 'Small'), ('M', 'Medium'), ('L', 'Large'), ('XL', 'Extra Large')], default='M', max_length=100),
        ),
    ]
