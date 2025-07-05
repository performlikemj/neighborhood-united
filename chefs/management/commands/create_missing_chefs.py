from django.core.management.base import BaseCommand
from django.db import transaction
from chefs.models import Chef, ChefRequest
from custom_auth.models import CustomUser, UserRole


class Command(BaseCommand):
    help = 'Creates Chef objects for users with approved ChefRequests but missing Chef objects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usernames',
            nargs='+',
            default=['tim', 'yuka'],
            help='Usernames to process (default: tim, yuka)'
        )

    def handle(self, *args, **options):
        usernames = options['usernames']
        self.stdout.write(f'Processing users: {", ".join(usernames)}')
        
        processed_count = 0
        error_count = 0
        
        for username in usernames:
            try:
                with transaction.atomic():
                    # Find the user
                    try:
                        user = CustomUser.objects.get(username=username)
                        self.stdout.write(f'Found user: {user.username}')
                    except CustomUser.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'User "{username}" not found. Skipping.')
                        )
                        continue
                    
                    # Check if Chef object already exists
                    if Chef.objects.filter(user=user).exists():
                        self.stdout.write(
                            self.style.WARNING(f'Chef object already exists for {username}. Skipping.')
                        )
                        continue
                    
                    # Find approved ChefRequest
                    try:
                        chef_request = ChefRequest.objects.get(user=user, is_approved=True)
                        self.stdout.write(f'Found approved ChefRequest for {username}')
                    except ChefRequest.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'No approved ChefRequest found for {username}. Skipping.')
                        )
                        continue
                    
                    # Create Chef object
                    chef = Chef.objects.create(user=user)
                    self.stdout.write(f'Created Chef object for {username}')
                    
                    # Transfer data from ChefRequest to Chef
                    if chef_request.experience:
                        chef.experience = chef_request.experience
                    if chef_request.bio:
                        chef.bio = chef_request.bio
                    if chef_request.profile_pic:
                        chef.profile_pic = chef_request.profile_pic
                    
                    chef.save()
                    self.stdout.write(f'Updated Chef data for {username}')
                    
                    # Set postal codes if there are any
                    if chef_request.requested_postalcodes.exists():
                        chef.serving_postalcodes.set(chef_request.requested_postalcodes.all())
                        postal_codes = list(chef_request.requested_postalcodes.values_list('code', flat=True))
                        self.stdout.write(f'Set postal codes for {username}: {postal_codes}')
                    
                    # Update or create UserRole
                    user_role, created = UserRole.objects.get_or_create(user=user)
                    user_role.is_chef = True
                    user_role.current_role = 'chef'
                    user_role.save()
                    
                    role_action = 'Created' if created else 'Updated'
                    self.stdout.write(f'{role_action} UserRole for {username}: is_chef=True, current_role=chef')
                    
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully processed {username}')
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error processing {username}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('')
        self.stdout.write(f'Processing complete:')
        self.stdout.write(f'  Successfully processed: {processed_count}')
        self.stdout.write(f'  Errors: {error_count}')
        
        if processed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {processed_count} Chef object(s)')
            ) 