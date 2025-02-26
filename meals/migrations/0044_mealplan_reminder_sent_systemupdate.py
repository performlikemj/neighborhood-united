# Generated by Django 4.2.10 on 2025-02-10 03:32

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('meals', '0043_mealplanmeal_meal_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='mealplan',
            name='reminder_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='SystemUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('sent_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
    ]
