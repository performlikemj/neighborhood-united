# Generated by Django 4.2 on 2024-02-06 08:03

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer_dashboard', '0016_alter_calorieintake_portion_size'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary', models.TextField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='summary', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
