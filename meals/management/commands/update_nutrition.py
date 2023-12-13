# yourapp/management/commands/update_nutrition.py

from django.core.management.base import BaseCommand
from menus.models import Dish

class Command(BaseCommand):
    help = 'Updates the nutritional information for all dishes'

    def handle(self, *args, **kwargs):
        dishes = Dish.objects.all()
        for dish in dishes:
            try:
                dish.get_nutritional_info()
                self.stdout.write(self.style.SUCCESS(f'Successfully updated dish {dish.id}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error updating dish {dish.id}: {e}'))
