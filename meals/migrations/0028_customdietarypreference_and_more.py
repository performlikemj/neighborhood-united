# Generated by Django 4.2.10 on 2024-10-02 07:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0027_alter_mealplanmeal_unique_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomDietaryPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('allowed', models.JSONField(blank=True, default=list)),
                ('excluded', models.JSONField(blank=True, default=list)),
            ],
        ),
        migrations.RemoveField(
            model_name='meal',
            name='custom_dietary_preference',
        ),
        migrations.AddField(
            model_name='meal',
            name='custom_dietary_preferences',
            field=models.ManyToManyField(blank=True, related_name='meals', to='meals.customdietarypreference'),
        ),
    ]
