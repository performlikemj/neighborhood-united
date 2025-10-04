from django.db import migrations
from django.contrib.postgres.operations import CreateExtension


class Migration(migrations.Migration):

    # Ensure this runs before the first VectorField usage in this app
    run_before = [
        ('meals', '0012_dish_dish_embedding_ingredient_ingredeint_embedding_and_more'),
    ]

    dependencies = [
        ('meals', '0011_remove_ordermeal_day_ordermeal_meal_plan_meal'),
    ]

    operations = [
        CreateExtension(name='vector'),
    ]

