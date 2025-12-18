# Generated manually for Sous Chef feature

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer_dashboard', '0036_remove_assistantemailtoken_is_active_and_more'),
        ('chefs', '0001_initial'),
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SousChefThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Sous Chef Conversation', max_length=255)),
                ('latest_response_id', models.CharField(blank=True, help_text='OpenAI response ID for continuation', max_length=255, null=True)),
                ('openai_input_history', models.JSONField(blank=True, default=list, help_text='Conversation history for OpenAI context')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sous_chef_threads', to='chefs.chef')),
                ('customer', models.ForeignKey(blank=True, help_text='Platform customer this conversation is about', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sous_chef_threads', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(blank=True, help_text='CRM lead this conversation is about', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sous_chef_threads', to='crm.lead')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SousChefMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('chef', 'Chef'), ('assistant', 'Assistant')], max_length=20)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tool_calls', models.JSONField(blank=True, default=list, help_text='Tool calls made during this response')),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='customer_dashboard.souschefthread')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='souschefthread',
            index=models.Index(fields=['chef', 'customer'], name='customer_da_chef_id_9e8a1c_idx'),
        ),
        migrations.AddIndex(
            model_name='souschefthread',
            index=models.Index(fields=['chef', 'lead'], name='customer_da_chef_id_2b5f3e_idx'),
        ),
        migrations.AddIndex(
            model_name='souschefthread',
            index=models.Index(fields=['chef', 'is_active'], name='customer_da_chef_id_a2c1b9_idx'),
        ),
    ]






