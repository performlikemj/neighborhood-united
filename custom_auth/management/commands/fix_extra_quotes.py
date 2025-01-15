# file: custom_auth/management/commands/fix_extra_quotes.py

from django.core.management.base import BaseCommand
from custom_auth.models import CustomUser
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Fix items in custom_allergies that have extra leading/trailing quotes."

    def handle(self, *args, **options):
        updated_count = 0
        self.stdout.write("Starting fix of extra quotes in custom_allergies...")

        for user in CustomUser.objects.all():
            allergies = user.custom_allergies  # This should be a Python list from Postgres array
            if not isinstance(allergies, list) or not allergies:
                continue  # Skip if empty or not a list

            # Check if we have strings with leading `'` or leading `["`
            fixed_list = []
            changed = False

            for item in allergies:
                # 'item' is a string, possibly with extra quotes. e.g. "'shrimp'"
                # We'll strip leading/trailing quotes
                new_item = item
                # If it starts with `'` and ends with `'`, remove them:
                if len(new_item) >= 2 and new_item.startswith("'") and new_item.endswith("'"):
                    new_item = new_item[1:-1]
                    changed = True

                # Also if new_item starts with `["` or something, we might remove bracket chars:
                # (only if it's obviously leftover from a previous parse attempt)
                # Example: new_item=="['shrimp'" => not well-formed
                # We'll do a quick replace for leading "['" or trailing "']"
                # Adjust logic to your exact data pattern
                if new_item.startswith("['"):
                    new_item = new_item[2:]
                    changed = True
                if new_item.endswith("']"):
                    new_item = new_item[:-2]
                    changed = True

                # strip whitespace
                new_item = new_item.strip()

                fixed_list.append(new_item)

            # If changed, save back to DB
            if changed:
                user.custom_allergies = fixed_list
                user.save()
                updated_count += 1
                self.stdout.write(
                    f"Updated user {user.username} custom_allergies from {allergies} to {fixed_list}"
                )

        self.stdout.write(
            f"Fix complete. {updated_count} user(s) updated."
        )