from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chef_services', '0004_alter_chefservicepricetier_desired_unit_amount_cents'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chefserviceoffering',
            name='max_travel_miles',
            field=models.PositiveIntegerField(blank=True, default=1, null=True),
        ),
    ]
