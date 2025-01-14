from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

class Command(BaseCommand):
    help = "Normalize custom_allergies field by converting comma-separated strings into a standardized format."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all()

        updated_count = 0
        self.stdout.write(self.style.NOTICE("Starting normalization of custom_allergies..."))

        for user in users:
            original = user.custom_allergies
            if original and isinstance(original, str):
                # Split by commas
                allergies_list = [a.strip() for a in original.split(',') if a.strip()]
                if allergies_list:
                    # Rejoin into a clean, comma-separated string without leading/trailing spaces
                    normalized = ",".join(allergies_list)
                    if normalized != original:
                        user.custom_allergies = normalized
                        user.save()
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Updated user {user.username} custom_allergies to: {normalized}"
                        ))
                else:
                    # If the list ends up empty after stripping, 
                    # it means original was empty or just whitespace.
                    # Set it to an empty string to be consistent.
                    if original.strip():
                        user.custom_allergies = ""
                        user.save()
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Cleared custom_allergies for user {user.username} as it had no valid entries."
                        ))

        self.stdout.write(self.style.SUCCESS(f"Normalization complete. {updated_count} user(s) updated."))