from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chef_services', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefserviceoffering',
            name='stripe_product_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='chefservicepricetier',
            name='desired_unit_amount_cents',
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.AddField(
            model_name='chefservicepricetier',
            name='last_price_sync_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chefservicepricetier',
            name='price_synced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chefservicepricetier',
            name='price_sync_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('success', 'Success'), ('error', 'Error')], default='pending', max_length=10),
        ),
        migrations.AlterField(
            model_name='chefservicepricetier',
            name='stripe_price_id',
            field=models.CharField(blank=True, help_text='Linked Stripe Price ID', max_length=200, null=True),
        ),
        migrations.AddConstraint(
            model_name='chefservicepricetier',
            constraint=models.CheckConstraint(check=models.Q(('desired_unit_amount_cents__gte', 50)), name='tier_desired_amount_min_50'),
        ),
    ]
