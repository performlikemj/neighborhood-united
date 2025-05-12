# Generated manually

from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0061_alter_dietarypreference_name'),  # Updated to reference the latest migration
    ]

    operations = [
        # Add the unique constraint
        migrations.AddConstraint(
            model_name='chefmealorder',
            constraint=models.UniqueConstraint(condition=Q(status__in=['placed', 'confirmed']), fields=('customer', 'meal_event'), name='uniq_active_order_per_event'),
        ),
    ] 