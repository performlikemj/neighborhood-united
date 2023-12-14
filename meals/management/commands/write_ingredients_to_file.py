from django.core.management.base import BaseCommand
from meals.models import Ingredient

class Command(BaseCommand):
    help = 'Writes the name and calories of all ingredients to a file'

    def handle(self, *args, **options):
        with open('ingredients.txt', 'a') as f:
            for ingredient in Ingredient.objects.all():
                f.write(f'{ingredient.name}: {ingredient.calories}\n')

        self.stdout.write(self.style.SUCCESS('Successfully wrote ingredients to file'))