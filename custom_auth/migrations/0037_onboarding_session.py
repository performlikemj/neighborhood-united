from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0036_remove_customuser_preferred_servings_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guest_id', models.CharField(max_length=40, unique=True)),
                ('data', models.JSONField(default=dict)),
                ('completed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
