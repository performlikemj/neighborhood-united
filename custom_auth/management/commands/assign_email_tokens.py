import uuid
from django.core.management.base import BaseCommand, CommandError
from custom_auth.models import CustomUser
from django.db import transaction

class Command(BaseCommand):
    help = 'Assigns a unique email_token (UUID) to all CustomUser objects that do not already have one.'

    def handle(self, *args, **options):
        users_without_token = CustomUser.objects.filter(email_token__isnull=True)
        updated_count = 0
        skipped_count = 0

        if not users_without_token.exists():
            self.stdout.write(self.style.SUCCESS('All users already have an email_token.'))
            return

        self.stdout.write(f'Found {users_without_token.count()} users without an email_token. Processing...')

        with transaction.atomic(): # Ensure all updates are processed or none are
            for user in users_without_token:
                try:
                    # Loop to ensure uniqueness, though direct collision is astronomically rare with UUIDv4
                    # and database unique constraint will catch it anyway.
                    # This explicit loop is more for absolute certainty if not relying solely on DB constraint during generation.
                    while True:
                        new_token = uuid.uuid4()
                        if not CustomUser.objects.filter(email_token=new_token).exists():
                            user.email_token = new_token
                            user.save(update_fields=['email_token'])
                            updated_count += 1
                            self.stdout.write(self.style.SUCCESS(f'Successfully assigned token to {user.username}'))
                            break
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'Error updating user {user.username} (ID: {user.id}): {e}'))
                    skipped_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Finished assigning email tokens.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} users.'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped_count} users due to errors.')) 