# Generated migration for memberships app

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('chefs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChefMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_customer_id', models.CharField(blank=True, help_text='Stripe Customer ID for this chef', max_length=200, null=True)),
                ('stripe_subscription_id', models.CharField(blank=True, help_text='Stripe Subscription ID for the membership', max_length=200, null=True)),
                ('billing_cycle', models.CharField(choices=[('monthly', 'Monthly ($20/month)'), ('annual', 'Annual ($204/year)'), ('free', 'Free (Founding Member)')], default='monthly', max_length=10)),
                ('status', models.CharField(choices=[('trial', 'Trial'), ('active', 'Active'), ('past_due', 'Past Due'), ('cancelled', 'Cancelled'), ('paused', 'Paused'), ('founding', 'Founding Member')], default='trial', max_length=20)),
                ('is_founding_member', models.BooleanField(default=False, help_text='Founding members get free access during the testing phase')),
                ('founding_member_notes', models.TextField(blank=True, help_text='Notes about why this chef is a founding member')),
                ('trial_started_at', models.DateTimeField(blank=True, help_text='When the trial period began', null=True)),
                ('trial_ends_at', models.DateTimeField(blank=True, help_text='When the trial period ends', null=True)),
                ('current_period_start', models.DateTimeField(blank=True, help_text='Start of current billing period', null=True)),
                ('current_period_end', models.DateTimeField(blank=True, help_text='End of current billing period', null=True)),
                ('started_at', models.DateTimeField(auto_now_add=True, help_text='When the membership was first created')),
                ('cancelled_at', models.DateTimeField(blank=True, help_text='When the membership was cancelled', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='membership', to='chefs.chef')),
            ],
            options={
                'verbose_name': 'Chef Membership',
                'verbose_name_plural': 'Chef Memberships',
            },
        ),
        migrations.CreateModel(
            name='MembershipPaymentLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_cents', models.PositiveIntegerField(help_text='Amount paid in cents')),
                ('currency', models.CharField(default='usd', max_length=3)),
                ('stripe_invoice_id', models.CharField(blank=True, help_text='Stripe Invoice ID', max_length=200, null=True)),
                ('stripe_payment_intent_id', models.CharField(blank=True, help_text='Stripe Payment Intent ID', max_length=200, null=True)),
                ('stripe_charge_id', models.CharField(blank=True, help_text='Stripe Charge ID', max_length=200, null=True)),
                ('period_start', models.DateTimeField(blank=True, null=True)),
                ('period_end', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(help_text='When the payment was processed')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('membership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_logs', to='memberships.chefmembership')),
            ],
            options={
                'verbose_name': 'Membership Payment Log',
                'verbose_name_plural': 'Membership Payment Logs',
                'ordering': ['-paid_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chefmembership',
            index=models.Index(fields=['status'], name='memberships_status_c63b5c_idx'),
        ),
        migrations.AddIndex(
            model_name='chefmembership',
            index=models.Index(fields=['stripe_customer_id'], name='memberships_stripe__7db9a0_idx'),
        ),
        migrations.AddIndex(
            model_name='chefmembership',
            index=models.Index(fields=['stripe_subscription_id'], name='memberships_stripe__1b7b3e_idx'),
        ),
        migrations.AddIndex(
            model_name='membershippaymentlog',
            index=models.Index(fields=['membership', '-paid_at'], name='memberships_members_a2d4e3_idx'),
        ),
        migrations.AddIndex(
            model_name='membershippaymentlog',
            index=models.Index(fields=['stripe_invoice_id'], name='memberships_stripe__4e5c8f_idx'),
        ),
    ]

