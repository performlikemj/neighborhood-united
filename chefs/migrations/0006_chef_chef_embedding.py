# Generated by Django 5.0.1 on 2024-02-26 02:31

import pgvector.django
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0005_alter_chef_profile_pic'),
    ]

    operations = [
        migrations.AddField(
            model_name='chef',
            name='chef_embedding',
            field=pgvector.django.VectorField(dimensions=1536, null=True),
        ),
    ]
