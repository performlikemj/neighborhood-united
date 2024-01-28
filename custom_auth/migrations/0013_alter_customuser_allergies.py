# Generated by Django 4.2 on 2024-01-27 18:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0012_alter_address_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='allergies',
            field=models.CharField(choices=[('Peanuts', 'Peanuts'), ('Tree nuts', 'Tree nuts'), ('Milk', 'Milk'), ('Egg', 'Egg'), ('Wheat', 'Wheat'), ('Soy', 'Soy'), ('Fish', 'Fish'), ('Shellfish', 'Shellfish'), ('Sesame', 'Sesame'), ('Mustard', 'Mustard'), ('Celery', 'Celery'), ('Lupin', 'Lupin'), ('Sulfites', 'Sulfites'), ('Molluscs', 'Molluscs'), ('Corn', 'Corn'), ('Gluten', 'Gluten'), ('Kiwi', 'Kiwi'), ('Latex', 'Latex'), ('Pine Nuts', 'Pine Nuts'), ('Sunflower Seeds', 'Sunflower Seeds'), ('Poppy Seeds', 'Poppy Seeds'), ('Fennel', 'Fennel'), ('Peach', 'Peach'), ('Banana', 'Banana'), ('Avocado', 'Avocado'), ('Chocolate', 'Chocolate'), ('Coffee', 'Coffee'), ('Cinnamon', 'Cinnamon'), ('Garlic', 'Garlic'), ('Chickpeas', 'Chickpeas'), ('Lentils', 'Lentils'), ('None', 'None')], default='None', max_length=70),
        ),
    ]