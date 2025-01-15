from django.core.management.base import BaseCommand
from custom_auth.models import CustomUser
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Normalize custom_allergies to a list for production migration"

    def handle(self, *args, **options):
        users_updated = 0
        self.stdout.write("Starting normalization of custom_allergies...")

        for user in CustomUser.objects.all():
            raw_value = user.custom_allergies
            if raw_value is None:
                # If it's None, set to an empty list
                user.custom_allergies = []
                user.save()
                users_updated += 1
                self.stdout.write(f"Updated user {user.username} custom_allergies to: []")
                continue

            if isinstance(raw_value, str):
                # Example: "No raw carrots,nuts"
                items = [x.strip() for x in raw_value.split(',') if x.strip()]
                normalized_items = []

                for item in items:
                    # If item starts with "No " or "no ", remove that token
                    # Or if you want to parse "No raw carrots" => "raw carrots"
                    if item.lower().startswith("no "):
                        # e.g. "no raw carrots" -> "raw carrots"
                        item = item[3:].strip()

                    # If the final item is empty after removal, skip it
                    if not item:
                        continue

                    normalized_items.append(item)

                # Now assign them as a python list
                user.custom_allergies = normalized_items
                user.save()
                users_updated += 1
                self.stdout.write(f"Updated user {user.username} custom_allergies to: {normalized_items}")

        self.stdout.write(f"Normalization complete. {users_updated} user(s) updated.")