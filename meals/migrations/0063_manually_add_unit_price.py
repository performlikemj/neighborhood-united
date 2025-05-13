# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0062_add_chef_meal_order_unique_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefmealorder',
            name='unit_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
    ] 