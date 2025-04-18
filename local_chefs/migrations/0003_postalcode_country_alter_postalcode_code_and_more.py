# Generated by Django 4.2.10 on 2025-03-15 20:55

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('local_chefs', '0002_alter_chefpostalcode_chef_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='postalcode',
            name='country',
            field=django_countries.fields.CountryField(default='US', max_length=2),
        ),
        migrations.AlterField(
            model_name='postalcode',
            name='code',
            field=models.CharField(max_length=15),
        ),
        migrations.AlterUniqueTogether(
            name='postalcode',
            unique_together={('code', 'country')},
        ),
    ]
