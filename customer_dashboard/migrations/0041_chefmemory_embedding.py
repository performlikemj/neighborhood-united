# customer_dashboard/migrations/0041_chefmemory_embedding.py
# Add vector embedding field to ChefMemory for semantic search

from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0040_remove_health_tracking_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefmemory',
            name='embedding',
            field=pgvector.django.VectorField(
                blank=True, 
                dimensions=1536, 
                help_text='OpenAI embedding for semantic search', 
                null=True
            ),
        ),
    ]
