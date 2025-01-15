from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
import ast

class Command(BaseCommand):
    help = "Copy data from custom_allergies text field to custom_allergies_array (ArrayField)."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()

        updated_count = 0
        self.stdout.write(self.style.NOTICE("Starting copy of custom_allergies to custom_allergies_array..."))

        for user in users:
            old_val = user.custom_allergies

            # Case 1: If old_val is None or empty, set an empty list
            if not old_val:
                user.custom_allergies_array = []
                user.save()
                updated_count += 1
                continue

            # Case 2: Try interpreting old_val as a Python literal (e.g. "[‘shrimp’, ‘walnuts’]")
            # If that fails, fallback to comma-splitting
            try:
                parsed = ast.literal_eval(old_val)  # e.g. "[‘shrimp’, 'walnuts']"
                if isinstance(parsed, list):
                    # Force each item to be str and strip whitespace
                    user.custom_allergies_array = [str(x).strip() for x in parsed if x]
                else:
                    # fallback if literal_eval is not a list
                    user.custom_allergies_array = [
                        s.strip() for s in old_val.split(',') if s.strip()
                    ]
            except (SyntaxError, ValueError, TypeError):
                # fallback for messy data or parse errors
                user.custom_allergies_array = [
                    s.strip() for s in old_val.split(',') if s.strip()
                ]

            # Convert empty or weird leftover data to a genuine empty list
            if not user.custom_allergies_array:
                user.custom_allergies_array = []

            user.save()
            updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Copy complete. {updated_count} user(s) updated."
        ))
        self.stdout.write(self.style.NOTICE(
            "Now you can remove the old custom_allergies field from the model and rename "
            "custom_allergies_array to custom_allergies."
        ))