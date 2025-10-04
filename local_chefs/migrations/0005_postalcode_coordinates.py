from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('local_chefs', '0004_add_display_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='postalcode',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='postalcode',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='postalcode',
            name='geocoded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
