# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0064_fix_chefmealorder_constraints'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Database operations (none needed, the previous migration handled it)
            [],
            
            # State operations to ensure Django's internal state is correct
            [
                migrations.AlterUniqueTogether(
                    name='chefmealorder',
                    unique_together=set(),
                ),
            ]
        ),
    ] 