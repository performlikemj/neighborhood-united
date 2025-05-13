# chefs/management/commands/update_chef_embeddings.py
from django.core.management.base import BaseCommand
from meals.meal_embedding import update_chef_embeddings  # Ensure this is the correct path to your task

class Command(BaseCommand):
    help = 'Triggers asynchronous update of embeddings for all chefs.'

    def handle(self, *args, **options):
        update_chef_embeddings.delay()  # Enqueue the task
        self.stdout.write(self.style.SUCCESS('Successfully triggered chef embeddings update task.'))
