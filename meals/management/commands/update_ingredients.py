from django.core.management.base import BaseCommand
from meals.models import Ingredient
from meals.views import get_ingredient_info, search_ingredients

class Command(BaseCommand):
    help = 'Updates all ingredients with calories and spoonacular_id from the Spoonacular API'

    def handle(self, *args, **options):
        for ingredient in Ingredient.objects.all():
            # If spoonacular_id is not set, search for the ingredient by name
            if ingredient.spoonacular_id is None:
                search_results = search_ingredients(ingredient.name)
                exact_match = next((result for result in search_results['results'] if result['name'].lower() == ingredient.name.lower()), None)
                if exact_match:
                    # Set the spoonacular_id to the id of the exact match
                    ingredient.spoonacular_id = exact_match['id']
                else:
                    # If no exact match, skip this ingredient
                    self.stdout.write(self.style.WARNING(f'Could not find spoonacular_id for ingredient "{ingredient.name}"'))
                    continue

            # Get ingredient info from Spoonacular API
            ingredient_info = get_ingredient_info(ingredient.spoonacular_id)
            calories = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Calories'), None)

            # Update ingredient with calories
            ingredient.calories = calories
            ingredient.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully updated ingredient "{ingredient.name}"'))