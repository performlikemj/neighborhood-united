from django.core.management.base import BaseCommand
from custom_auth.models import CustomUser
import ast

class Command(BaseCommand):
    help = 'Update allergies field data'

    def handle(self, *args, **options):
        for user in CustomUser.objects.all():
            if user.allergies:
                try:
                    user.allergies = ast.literal_eval(user.allergies)
                except ValueError:
                    self.stdout.write(self.style.ERROR(f'Failed to update allergies for user {user.id}'))
                    continue
            else:
                user.allergies = []
            user.save()

        self.stdout.write(self.style.SUCCESS('Successfully updated allergies field data'))