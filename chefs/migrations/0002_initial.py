# Generated by Django 4.2 on 2023-11-06 18:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('local_chefs', '0001_initial'),
        ('chefs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefrequest',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='chef',
            name='primary_postal_code',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='primary_chefs', to='local_chefs.postalcode'),
        ),
        migrations.AddField(
            model_name='chef',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
