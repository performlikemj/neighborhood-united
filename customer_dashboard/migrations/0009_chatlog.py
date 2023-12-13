# Generated by Django 4.2 on 2023-11-25 05:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer_dashboard', '0008_foodpreferences'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conversation', models.TextField()),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('chat_thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_log', to='customer_dashboard.chatthread')),
            ],
        ),
    ]