from django.core.management.base import BaseCommand
from meals.models import Meal, Dish, Ingredient
from django.conf import settings
from meals.meal_embedding import update_embeddings

class Command(BaseCommand):
    help = 'Triggers asynchronous update of embeddings for all meals, dishes, and ingredients.'

    def handle(self, *args, **options):
        update_embeddings.delay()
        self.stdout.write(self.style.SUCCESS('Successfully triggered embeddings update task.'))
