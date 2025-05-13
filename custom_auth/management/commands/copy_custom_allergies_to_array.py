from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

class Command(BaseCommand):
    help = "Copy data from the custom_allergies text field to the custom_allergies_array field (ArrayField)."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()

        updated_count = 0
        self.stdout.write(self.style.NOTICE("Starting copy of custom_allergies to custom_allergies_array..."))

        for user in users:
            old_val = user.custom_allergies
            if old_val is None:
                # If None, just set to empty list
                user.custom_allergies_array = []
            else:
                # old_val is a string (possibly empty or with commas)
                allergy_list = [a.strip() for a in old_val.split(',') if a.strip()]
                user.custom_allergies_array = allergy_list
            user.save()

        self.stdout.write(self.style.SUCCESS(
            f"Copy complete. {updated_count} user(s) updated."
        ))
        self.stdout.write(self.style.NOTICE(
            "Now you can remove the old custom_allergies field from the model and rename custom_allergies_array to custom_allergies."
        ))