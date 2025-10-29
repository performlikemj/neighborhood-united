# Generated manually for unified cart checkout

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0070_mealplanbatchjob_mealplanbatchrequest'),
        ('chef_services', '0005_alter_chefserviceoffering_max_travel_miles'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='chef_service_orders',
            field=models.ManyToManyField(blank=True, related_name='carts', to='chef_services.chefserviceorder'),
        ),
    ]

