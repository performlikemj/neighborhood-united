# Generated migration for ChefPaymentLink model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chefs', '0025_update_prep_plan_commitment'),
        ('crm', '0003_lead_email_verification'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChefPaymentLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_cents', models.PositiveIntegerField(help_text='Payment amount in cents (e.g., 5000 = $50.00)')),
                ('currency', models.CharField(default='usd', max_length=3)),
                ('description', models.CharField(help_text='Description of what this payment is for', max_length=500)),
                ('stripe_payment_link_id', models.CharField(blank=True, help_text='Stripe Payment Link ID', max_length=200, null=True)),
                ('stripe_payment_link_url', models.URLField(blank=True, help_text='Shareable Stripe Payment Link URL', max_length=500, null=True)),
                ('stripe_price_id', models.CharField(blank=True, help_text='Stripe Price ID created for this payment', max_length=200, null=True)),
                ('stripe_product_id', models.CharField(blank=True, help_text='Stripe Product ID created for this payment', max_length=200, null=True)),
                ('stripe_checkout_session_id', models.CharField(blank=True, help_text='Stripe Checkout Session ID when payment is initiated', max_length=200, null=True)),
                ('stripe_payment_intent_id', models.CharField(blank=True, help_text='Stripe Payment Intent ID after successful payment', max_length=200, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Payment'), ('paid', 'Paid'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], default='draft', max_length=20)),
                ('recipient_email', models.EmailField(blank=True, help_text='Email address the payment link was sent to', max_length=254)),
                ('email_sent_at', models.DateTimeField(blank=True, help_text='When the payment link email was last sent', null=True)),
                ('email_send_count', models.PositiveIntegerField(default=0, help_text='Number of times the payment link has been emailed')),
                ('paid_at', models.DateTimeField(blank=True, help_text='When the payment was completed', null=True)),
                ('paid_amount_cents', models.PositiveIntegerField(blank=True, help_text='Actual amount paid (may differ due to fees)', null=True)),
                ('expires_at', models.DateTimeField(help_text='When this payment link expires')),
                ('internal_notes', models.TextField(blank=True, help_text='Internal notes for the chef (not shown to client)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_links', to='chefs.chef')),
                ('customer', models.ForeignKey(blank=True, help_text='For platform users', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chef_payment_links', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(blank=True, help_text='For off-platform clients (manual contacts)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_links', to='crm.lead')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['chef', 'status'], name='chefs_chefp_chef_id_payment_idx'),
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['chef', '-created_at'], name='chefs_chefp_chef_id_created_idx'),
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['lead', 'status'], name='chefs_chefp_lead_id_status_idx'),
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['customer', 'status'], name='chefs_chefp_cust_status_idx'),
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['stripe_payment_link_id'], name='chefs_chefp_stripe_link_idx'),
        ),
        migrations.AddIndex(
            model_name='chefpaymentlink',
            index=models.Index(fields=['stripe_checkout_session_id'], name='chefs_chefp_stripe_sess_idx'),
        ),
    ]



