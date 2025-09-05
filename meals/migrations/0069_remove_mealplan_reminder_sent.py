from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0068_meal_composed_dishes_mealdish'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mealplan',
            name='reminder_sent',
        ),
    ]

