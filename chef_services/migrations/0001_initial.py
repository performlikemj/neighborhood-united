from django.db import migrations, models
import django.db.models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('chefs', '0001_initial'),
        ('custom_auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChefServiceOffering',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_type', models.CharField(choices=[('home_chef', 'Personal Home Chef'), ('weekly_prep', 'Weekly Meal Prep')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('default_duration_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('max_travel_miles', models.PositiveIntegerField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_offerings', to='chefs.chef')),
            ],
        ),
        migrations.CreateModel(
            name='ChefServicePriceTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('household_min', models.PositiveIntegerField()),
                ('household_max', models.PositiveIntegerField(blank=True, null=True, help_text='Null means no upper bound')),
                ('currency', models.CharField(default='usd', max_length=10)),
                ('stripe_price_id', models.CharField(blank=True, max_length=200, null=True, help_text='Provided by MCP server')),
                ('is_recurring', models.BooleanField(default=False)),
                ('recurrence_interval', models.CharField(blank=True, choices=[('week', 'Per Week')], max_length=10, null=True)),
                ('active', models.BooleanField(default=True)),
                ('display_label', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('offering', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tiers', to='chef_services.chefserviceoffering')),
            ],
        ),
        migrations.CreateModel(
            name='ChefServiceOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('household_size', models.PositiveIntegerField()),
                ('service_date', models.DateField(blank=True, null=True)),
                ('service_start_time', models.TimeField(blank=True, null=True)),
                ('duration_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('special_requests', models.TextField(blank=True)),
                ('schedule_preferences', models.JSONField(blank=True, null=True)),
                ('stripe_session_id', models.CharField(blank=True, max_length=200, null=True)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=200, null=True)),
                ('is_subscription', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('awaiting_payment', 'Awaiting Payment'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('refunded', 'Refunded'), ('completed', 'Completed')], default='draft', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('address', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='custom_auth.address')),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='service_orders', to='chefs.chef')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='service_orders', to='custom_auth.customuser')),
                ('offering', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='chef_services.chefserviceoffering')),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='chef_services.chefservicepricetier')),
            ],
        ),
        migrations.AddConstraint(
            model_name='chefservicepricetier',
            constraint=models.CheckConstraint(check=models.Q(('household_min__gte', 1)), name='tier_household_min_gte_1'),
        ),
        migrations.AddConstraint(
            model_name='chefservicepricetier',
            constraint=models.CheckConstraint(check=(models.Q(('household_max__isnull', True)) | models.Q(('household_max__gte', django.db.models.F('household_min')))), name='tier_household_max_gte_min_or_null'),
        ),
        migrations.AddConstraint(
            model_name='chefservicepricetier',
            constraint=models.CheckConstraint(check=(models.Q(('is_recurring', False), ('recurrence_interval__isnull', True), _connector='AND') | models.Q(('is_recurring', True), ('recurrence_interval__isnull', False), _connector='AND')), name='tier_recurring_interval_consistency'),
        ),
        migrations.AddConstraint(
            model_name='chefserviceorder',
            constraint=models.CheckConstraint(check=models.Q(('household_size__gte', 1)), name='order_household_size_gte_1'),
        ),
    ]
