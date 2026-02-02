# Generated migration for chef profile fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0035_proactive_engine_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefworkspace',
            name='chef_nickname',
            field=models.CharField(
                blank=True,
                default='',
                help_text="How Sous Chef addresses the chef (e.g., 'Chef Marcus', 'Marcus')",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='chefworkspace',
            name='chef_specialties',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Chef's specialties: ['comfort', 'meal-prep', 'health']",
            ),
        ),
        migrations.AddField(
            model_name='chefworkspace',
            name='sous_chef_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Custom name for the assistant (default: 'Sous Chef')",
                max_length=50,
            ),
        ),
    ]
