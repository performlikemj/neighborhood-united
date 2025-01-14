# chefs/migrations/0005_install_pgvector.py
from django.db import migrations
from django.contrib.postgres.operations import CreateExtension

class Migration(migrations.Migration):

    dependencies = [
        # If your previously existing migration is '0005_alter_chef_profile_pic',
        # then set that here. If the last known migration was '0004_something',
        # adjust accordingly so this runs right after your last existing migration
        ('chefs', '0005_alter_chef_profile_pic'),
    ]

    operations = [
        CreateExtension(name='vector'),
    ]