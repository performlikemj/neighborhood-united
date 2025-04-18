# Generated by Django 4.2.10 on 2025-02-27 03:02

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0007_merge_0005_install_pgvector_0006_chef_chef_embedding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('meals', '0044_mealplan_reminder_sent_systemupdate'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChefMealEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_date', models.DateField()),
                ('event_time', models.TimeField()),
                ('order_cutoff_time', models.DateTimeField(help_text='Deadline for placing orders')),
                ('max_orders', models.PositiveIntegerField(help_text='Maximum number of orders the chef can fulfill')),
                ('min_orders', models.PositiveIntegerField(default=1, help_text='Minimum number of orders needed to proceed')),
                ('base_price', models.DecimalField(decimal_places=2, help_text='Starting price per order', max_digits=6)),
                ('current_price', models.DecimalField(decimal_places=2, help_text='Current price based on number of orders', max_digits=6)),
                ('min_price', models.DecimalField(decimal_places=2, help_text='Minimum price per order', max_digits=6)),
                ('orders_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('open', 'Open for Orders'), ('closed', 'Closed for Orders'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='scheduled', max_length=20)),
                ('description', models.TextField(blank=True)),
                ('special_instructions', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_events', to='chefs.chef')),
                ('meal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='meals.meal')),
            ],
            options={
                'ordering': ['event_date', 'event_time'],
                'unique_together': {('chef', 'meal', 'event_date', 'event_time')},
            },
        ),
        migrations.CreateModel(
            name='ChefMealOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('price_paid', models.DecimalField(decimal_places=2, max_digits=6)),
                ('status', models.CharField(choices=[('placed', 'Placed'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('refunded', 'Refunded'), ('completed', 'Completed')], default='placed', max_length=20)),
                ('stripe_payment_intent_id', models.CharField(blank=True, max_length=255, null=True)),
                ('stripe_refund_id', models.CharField(blank=True, max_length=255, null=True)),
                ('special_requests', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('meal_event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='meals.chefmealevent')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chef_meal_orders', to='meals.order')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PlatformFeeConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fee_percentage', models.DecimalField(decimal_places=2, help_text='Platform fee percentage (0-100)', max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='StripeConnectAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_account_id', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stripe_account', to='chefs.chef')),
            ],
        ),
        migrations.CreateModel(
            name='PaymentLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('charge', 'Charge'), ('refund', 'Refund'), ('payout', 'Payout to Chef'), ('adjustment', 'Manual Adjustment')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stripe_id', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(max_length=50)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chef', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='chefs.chef')),
                ('chef_meal_order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_logs', to='meals.chefmealorder')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_logs', to='meals.order')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ChefMealReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_reviews', to='chefs.chef')),
                ('chef_meal_order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review', to='meals.chefmealorder')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('meal_event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='meals.chefmealevent')),
            ],
            options={
                'unique_together': {('customer', 'meal_event')},
            },
        ),
    ]
