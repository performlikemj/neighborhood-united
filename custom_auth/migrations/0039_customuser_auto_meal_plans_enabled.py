from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0038_customuser_measurement_system"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="auto_meal_plans_enabled",
            field=models.BooleanField(
                default=True,
                help_text="If False, do not auto-generate weekly meal plans.",
            ),
        ),
    ]

