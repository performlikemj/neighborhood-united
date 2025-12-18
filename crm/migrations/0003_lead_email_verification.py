# Generated migration for Lead email verification fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_add_household_and_dietary_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='email_verified',
            field=models.BooleanField(default=False, help_text="Whether the contact's email has been verified"),
        ),
        migrations.AddField(
            model_name='lead',
            name='email_verification_token',
            field=models.CharField(blank=True, help_text='Secure token for email verification', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='email_verification_sent_at',
            field=models.DateTimeField(blank=True, help_text='When the verification email was last sent', null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='email_verified_at',
            field=models.DateTimeField(blank=True, help_text='When the email was verified', null=True),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['email_verification_token'], name='crm_lead_email_v_a4e8b5_idx'),
        ),
    ]





