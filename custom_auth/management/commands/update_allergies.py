from django.core.management.base import BaseCommand
from custom_auth.models import CustomUser
import ast

class Command(BaseCommand):
    help = 'Update allergies field data'

    def handle(self, *args, **options):
        for user in CustomUser.objects.all():
            if user.allergies:
                try:
                    allergies = ast.literal_eval(user.allergies)
                    if isinstance(allergies, list):
                        user.allergies = allergies
                    else:
                        user.allergies = [user.allergies]
                except ValueError:
                    user.allergies = [user.allergies] if user.allergies else []
            else:
                user.allergies = []
            user.save()

        self.stdout.write(self.style.SUCCESS('Successfully updated allergies field data'))