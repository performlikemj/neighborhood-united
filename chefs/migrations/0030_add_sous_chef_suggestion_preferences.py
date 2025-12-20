# Generated manually for sous chef suggestion preferences

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0029_add_chef_default_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='chef',
            name='sous_chef_suggestions_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Enable contextual AI suggestions from Sous Chef'
            ),
        ),
        migrations.AddField(
            model_name='chef',
            name='sous_chef_suggestion_frequency',
            field=models.CharField(
                choices=[
                    ('often', 'Often'),
                    ('sometimes', 'Sometimes'),
                    ('rarely', 'Rarely')
                ],
                default='sometimes',
                help_text='How often to show contextual suggestions',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='chef',
            name='dismissed_suggestion_types',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of suggestion types the chef has dismissed permanently'
            ),
        ),
    ]
