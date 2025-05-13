# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0063_manually_add_unit_price'),
    ]

    operations = [
        # Simply mark as completed rather than trying to alter database directly
        migrations.RunSQL(
            # Forward SQL - a simple no-op 
            "SELECT 1;",
            # Reverse SQL
            "SELECT 1;"
        ),
    ] 