# chefs/migrations/0034_proactive_and_onboarding.py
# Proactive notifications and onboarding state

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chefs', '0033_sous_chef_memory_system'),
        ('crm', '0001_initial'),
    ]

    operations = [
        # ChefProactiveSettings
        migrations.CreateModel(
            name='ChefProactiveSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proactive_enabled', models.BooleanField(default=False, help_text='Master switch for proactive notifications')),
                ('frequency', models.CharField(
                    choices=[
                        ('realtime', 'As things happen'),
                        ('daily', 'Daily digest'),
                        ('weekly', 'Weekly summary'),
                        ('manual', 'Only when I ask')
                    ],
                    default='manual',
                    max_length=20
                )),
                ('notify_birthdays', models.BooleanField(default=False)),
                ('notify_anniversaries', models.BooleanField(default=False)),
                ('notify_followups', models.BooleanField(default=False)),
                ('notify_todos', models.BooleanField(default=False)),
                ('notify_seasonal', models.BooleanField(default=False)),
                ('notify_milestones', models.BooleanField(default=False)),
                ('occasion_lead_days', models.PositiveIntegerField(default=7)),
                ('followup_threshold_days', models.PositiveIntegerField(default=21)),
                ('channel_inapp', models.BooleanField(default=True)),
                ('channel_email', models.BooleanField(default=False)),
                ('channel_push', models.BooleanField(default=False)),
                ('quiet_start', models.TimeField(blank=True, null=True)),
                ('quiet_end', models.TimeField(blank=True, null=True)),
                ('timezone', models.CharField(default='UTC', max_length=50)),
                ('last_prompted_at', models.DateTimeField(blank=True, null=True)),
                ('never_prompt', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='proactive_settings',
                    to='chefs.chef'
                )),
            ],
            options={
                'verbose_name': 'Chef Proactive Settings',
                'verbose_name_plural': 'Chef Proactive Settings',
            },
        ),
        
        # ChefOnboardingState
        migrations.CreateModel(
            name='ChefOnboardingState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('welcomed', models.BooleanField(default=False)),
                ('setup_started', models.BooleanField(default=False)),
                ('setup_completed', models.BooleanField(default=False)),
                ('setup_skipped', models.BooleanField(default=False)),
                ('personality_set', models.BooleanField(default=False)),
                ('personality_choice', models.CharField(blank=True, default='', max_length=50)),
                ('first_dish_added', models.BooleanField(default=False)),
                ('first_dish_added_at', models.DateTimeField(blank=True, null=True)),
                ('first_client_added', models.BooleanField(default=False)),
                ('first_client_added_at', models.DateTimeField(blank=True, null=True)),
                ('first_order_completed', models.BooleanField(default=False)),
                ('first_order_completed_at', models.DateTimeField(blank=True, null=True)),
                ('first_memory_saved', models.BooleanField(default=False)),
                ('first_memory_saved_at', models.DateTimeField(blank=True, null=True)),
                ('first_meal_plan_created', models.BooleanField(default=False)),
                ('first_meal_plan_created_at', models.DateTimeField(blank=True, null=True)),
                ('tips_shown', models.JSONField(blank=True, default=list)),
                ('tips_dismissed', models.JSONField(blank=True, default=list)),
                ('sous_chef_conversations', models.PositiveIntegerField(default=0)),
                ('last_sous_chef_chat', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='onboarding_state',
                    to='chefs.chef'
                )),
            ],
            options={
                'verbose_name': 'Chef Onboarding State',
                'verbose_name_plural': 'Chef Onboarding States',
            },
        ),
        
        # ChefNotification
        migrations.CreateModel(
            name='ChefNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(
                    choices=[
                        ('birthday', 'Birthday Reminder'),
                        ('anniversary', 'Anniversary Reminder'),
                        ('followup', 'Follow-up Suggestion'),
                        ('todo', 'Todo Reminder'),
                        ('seasonal', 'Seasonal Suggestion'),
                        ('milestone', 'Client Milestone'),
                        ('tip', 'Feature Tip'),
                        ('welcome', 'Welcome Message'),
                        ('system', 'System Notification')
                    ],
                    max_length=20
                )),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('action_type', models.CharField(blank=True, max_length=50)),
                ('action_payload', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('sent', 'Sent'),
                        ('read', 'Read'),
                        ('dismissed', 'Dismissed'),
                        ('failed', 'Failed')
                    ],
                    default='pending',
                    max_length=20
                )),
                ('sent_inapp', models.BooleanField(default=False)),
                ('sent_email', models.BooleanField(default=False)),
                ('sent_push', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('dismissed_at', models.DateTimeField(blank=True, null=True)),
                ('scheduled_for', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to='chefs.chef'
                )),
                ('related_client', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
                ('related_lead', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='crm.lead'
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # Indexes
        migrations.AddIndex(
            model_name='chefnotification',
            index=models.Index(fields=['chef', 'status'], name='chefs_notif_chef_status_idx'),
        ),
        migrations.AddIndex(
            model_name='chefnotification',
            index=models.Index(fields=['chef', '-created_at'], name='chefs_notif_chef_created_idx'),
        ),
        migrations.AddIndex(
            model_name='chefnotification',
            index=models.Index(fields=['status', 'scheduled_for'], name='chefs_notif_sched_idx'),
        ),
    ]
