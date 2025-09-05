from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0037_onboarding_session'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='measurement_system',
            field=models.CharField(choices=[('US', 'US Customary'), ('METRIC', 'Metric')], default='METRIC', max_length=10),
        ),
    ]

