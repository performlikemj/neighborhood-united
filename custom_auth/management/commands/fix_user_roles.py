from django.core.management.base import BaseCommand
from django.db import transaction
from custom_auth.models import CustomUser, UserRole


class Command(BaseCommand):
    help = 'Create UserRole instances for all users who don\'t have one, setting their role to customer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Show what would be done without actually making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all users who don't have a UserRole
        users_without_roles = CustomUser.objects.filter(userrole__isnull=True)
        total_users = users_without_roles.count()
        
        if total_users == 0:
            self.stdout.write(
                self.style.SUCCESS('All users already have roles assigned.')
            )
            return
        
        self.stdout.write(f'Found {total_users} users without roles.')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
            for user in users_without_roles:
                self.stdout.write(f'Would create customer role for: {user.username} ({user.email})')
        else:
            # Create UserRole instances for users without roles
            with transaction.atomic():
                roles_created = 0
                for user in users_without_roles:
                    UserRole.objects.create(
                        user=user,
                        is_chef=False,
                        current_role='customer'
                    )
                    roles_created += 1
                    self.stdout.write(f'Created customer role for: {user.username} ({user.email})')
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created {roles_created} customer roles.')
                )
        
        # Also show users who already have roles
        users_with_roles = CustomUser.objects.filter(userrole__isnull=False)
        self.stdout.write(f'\nUsers with existing roles: {users_with_roles.count()}')
        
        if users_with_roles.count() > 0:
            self.stdout.write('Existing roles:')
            for user in users_with_roles:
                role = user.userrole.current_role
                self.stdout.write(f'  {user.username} ({user.email}): {role}') 