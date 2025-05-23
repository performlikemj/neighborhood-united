# Generated by Django 4.2.10 on 2025-04-28 11:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer_dashboard', '0029_backfill_response_ids_and_latest'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatthread',
            name='announcement_shown',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='WeeklyAnnouncement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField()),
                ('country', django_countries.fields.CountryField(blank=True, max_length=2, null=True)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-week_start', 'country'],
                'unique_together': {('week_start', 'country')},
            },
        ),
    ]
