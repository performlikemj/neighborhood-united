# Generated migration to rename postal code fields for clarity
# input_postalcode -> normalized_postalcode (stores normalized format for lookups)
# display_postalcode -> original_postalcode (stores original user input)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0040_add_sample_plan_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='address',
            old_name='input_postalcode',
            new_name='normalized_postalcode',
        ),
        migrations.RenameField(
            model_name='address',
            old_name='display_postalcode',
            new_name='original_postalcode',
        ),
        migrations.AlterField(
            model_name='address',
            name='normalized_postalcode',
            field=models.CharField(
                blank=True,
                help_text='Normalized format for lookups',
                max_length=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='address',
            name='original_postalcode',
            field=models.CharField(
                blank=True,
                help_text='Original user input format',
                max_length=15,
                null=True,
            ),
        ),
    ]

