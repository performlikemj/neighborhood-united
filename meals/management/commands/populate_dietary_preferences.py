from django.core.management.base import BaseCommand
from django.db import connection
from meals.models import DietaryPreference, Meal

class Command(BaseCommand):
    help = 'Populates the DietaryPreference model with predefined dietary preferences and updates existing meals'

    def handle(self, *args, **kwargs):
        # List of dietary preferences (previously in DIETARY_CHOICES)
        dietary_preferences = [
            'Vegan', 'Vegetarian', 'Pescatarian', 'Gluten-Free', 'Keto', 'Paleo',
            'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein',
            'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP',
            'Diabetic-Friendly', 'Everything'
        ]

        # Create or get each dietary preference in the model
        for preference in dietary_preferences:
            obj, created = DietaryPreference.objects.get_or_create(name=preference)
            if created:
                self.stdout.write(self.style.SUCCESS(f'DietaryPreference "{preference}" created.'))
            else:
                self.stdout.write(f'DietaryPreference "{preference}" already exists.')

        # Check if the old 'dietary_preference' field exists in the Meal model
        with connection.cursor() as cursor:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'meals_meal' AND column_name = 'dietary_preference'")
            column_exists = cursor.fetchone() is not None

        if column_exists:
            # Update meals that have an old dietary preference to use the new ManyToMany field
            for meal in Meal.objects.all():
                if meal.dietary_preference:  # If the old field is set
                    preference = DietaryPreference.objects.filter(name=meal.dietary_preference).first()
                    if preference:
                        meal.dietary_preferences.add(preference)
                        meal.save()
                        self.stdout.write(f'Updated Meal "{meal.name}" with DietaryPreference "{preference.name}".')

        self.stdout.write(self.style.SUCCESS('Finished populating dietary preferences and updating meals.'))
