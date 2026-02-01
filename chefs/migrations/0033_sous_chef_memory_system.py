# Generated migration for Sous Chef memory system
# chefs/migrations/0033_sous_chef_memory_system.py

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import pgvector.django


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chefs', '0032_add_chef_is_live'),
        ('crm', '0001_initial'),  # Assuming CRM app exists
    ]

    operations = [
        # ChefWorkspace - personality and configuration
        migrations.CreateModel(
            name='ChefWorkspace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soul_prompt', models.TextField(blank=True, default='', help_text='Sous Chef personality, tone, and communication style')),
                ('business_rules', models.TextField(blank=True, default='', help_text='Operating constraints: hours, pricing, policies, boundaries')),
                ('enabled_tools', models.JSONField(blank=True, default=list, help_text='List of tool names the chef has enabled')),
                ('tool_preferences', models.JSONField(blank=True, default=dict, help_text='Per-tool configuration overrides')),
                ('include_analytics', models.BooleanField(default=True, help_text='Include business analytics in context')),
                ('include_seasonal', models.BooleanField(default=True, help_text='Include seasonal ingredient suggestions')),
                ('auto_memory_save', models.BooleanField(default=True, help_text='Automatically save important insights to memory')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='workspace', to='chefs.chef')),
            ],
            options={
                'verbose_name': 'Chef Workspace',
                'verbose_name_plural': 'Chef Workspaces',
            },
        ),
        
        # ClientContext - per-client preferences
        migrations.CreateModel(
            name='ClientContext',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(blank=True, help_text='How chef refers to this client', max_length=100)),
                ('summary', models.TextField(blank=True, help_text='Quick summary of this client (auto-generated or manual)')),
                ('cuisine_preferences', models.JSONField(blank=True, default=list, help_text='Preferred cuisines/styles')),
                ('flavor_profile', models.JSONField(blank=True, default=dict, help_text='Flavor preferences: spicy, sweet, etc.')),
                ('cooking_notes', models.TextField(blank=True, help_text='Notes on cooking for this client')),
                ('communication_style', models.CharField(blank=True, help_text='How client prefers to communicate', max_length=50)),
                ('special_occasions', models.JSONField(blank=True, default=list, help_text='Birthdays, anniversaries, etc.')),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_spent_cents', models.PositiveIntegerField(default=0)),
                ('first_order_date', models.DateField(blank=True, null=True)),
                ('last_order_date', models.DateField(blank=True, null=True)),
                ('profile_embedding', pgvector.django.VectorField(blank=True, dimensions=1536, help_text='Embedding of client preferences for similarity matching', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_contexts', to='chefs.chef')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chef_contexts', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chef_contexts', to='crm.lead')),
            ],
            options={
                'verbose_name': 'Client Context',
                'verbose_name_plural': 'Client Contexts',
            },
        ),
        
        # ClientContext unique constraints
        migrations.AddConstraint(
            model_name='clientcontext',
            constraint=models.UniqueConstraint(fields=['chef', 'client'], name='unique_chef_client_context'),
        ),
        migrations.AddConstraint(
            model_name='clientcontext',
            constraint=models.UniqueConstraint(fields=['chef', 'lead'], name='unique_chef_lead_context'),
        ),
        migrations.AddIndex(
            model_name='clientcontext',
            index=models.Index(fields=['chef', 'client'], name='chefs_client_chef_client_idx'),
        ),
        migrations.AddIndex(
            model_name='clientcontext',
            index=models.Index(fields=['chef', 'lead'], name='chefs_client_chef_lead_idx'),
        ),
        
        # SousChefUsage - token tracking
        migrations.CreateModel(
            name='SousChefUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('input_tokens', models.PositiveIntegerField(default=0)),
                ('output_tokens', models.PositiveIntegerField(default=0)),
                ('conversation_tokens', models.PositiveIntegerField(default=0)),
                ('memory_search_tokens', models.PositiveIntegerField(default=0)),
                ('embedding_tokens', models.PositiveIntegerField(default=0)),
                ('request_count', models.PositiveIntegerField(default=0)),
                ('tool_call_count', models.PositiveIntegerField(default=0)),
                ('memory_saves', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sous_chef_usage', to='chefs.chef')),
            ],
            options={
                'ordering': ['-date'],
            },
        ),
        migrations.AddConstraint(
            model_name='souschefusage',
            constraint=models.UniqueConstraint(fields=['chef', 'date'], name='unique_chef_date_usage'),
        ),
        migrations.AddIndex(
            model_name='souschefusage',
            index=models.Index(fields=['chef', '-date'], name='chefs_usage_chef_date_idx'),
        ),
    ]
