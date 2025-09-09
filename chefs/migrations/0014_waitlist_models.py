from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0013_chefdefaultbanner_chef_banner_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChefWaitlistConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False, help_text='Enable chef waitlist feature globally')),
                ('cooldown_hours', models.PositiveIntegerField(default=24, help_text='Minimum hours a chef must be inactive before a new activation triggers notifications')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Chef Waitlist Config',
                'verbose_name_plural': 'Chef Waitlist Config',
            },
        ),
        migrations.CreateModel(
            name='ChefAvailabilityState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=False)),
                ('activation_epoch', models.PositiveIntegerField(default=0, help_text='Increments each time the chef becomes active after a cooldown')),
                ('last_activated_at', models.DateTimeField(blank=True, null=True)),
                ('last_deactivated_at', models.DateTimeField(blank=True, null=True)),
                ('chef', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='availability', to='chefs.chef')),
            ],
            options={
                'verbose_name': 'Chef Availability State',
                'verbose_name_plural': 'Chef Availability States',
            },
        ),
        migrations.CreateModel(
            name='ChefWaitlistSubscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('last_notified_epoch', models.PositiveIntegerField(blank=True, null=True)),
                ('last_notified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chef', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='waitlist_subscriptions', to='chefs.chef')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chef_waitlist_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['chef', 'active'], name='chefs_chefw_chef_id_a8d8e1_idx'),
                    models.Index(fields=['user', 'active'], name='chefs_chefw_user_id_a7b4a9_idx'),
                ],
            },
        ),
        migrations.AlterUniqueTogether(
            name='chefwaitlistsubscription',
            unique_together={('user', 'chef', 'active')},
        ),
    ]

