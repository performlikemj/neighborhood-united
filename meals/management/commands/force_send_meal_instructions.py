from django.core.management.base import BaseCommand, CommandError
from meals.meal_instructions import force_send_meal_instructions
import json


class Command(BaseCommand):
    help = 'Force send meal instructions for a specific user (bypasses normal timing restrictions)'

    def add_arguments(self, parser):
        parser.add_argument('user_email', type=str, help='Email of the user to send instructions to')
        parser.add_argument(
            '--date',
            type=str,
            help='Target date in YYYY-MM-DD format (defaults to tomorrow)',
            default=None
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format',
        )

    def handle(self, *args, **options):
        user_email = options['user_email']
        target_date = options['date']
        
        self.stdout.write(f"Force sending meal instructions for: {user_email}")
        if target_date:
            self.stdout.write(f"Target date: {target_date}")
        
        # Call the force send task
        result = force_send_meal_instructions(user_email, target_date)
        
        if options['json']:
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            self._print_result(result)
    
    def _print_result(self, result):
        """Print result in human-readable format"""
        
        if result['status'] == 'error':
            self.stdout.write(
                self.style.ERROR(f"ERROR: {result['message']}")
            )
            return
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("FORCE SEND RESULTS")
        self.stdout.write("="*50)
        
        self.stdout.write(f"\nUser: {result['user_email']}")
        self.stdout.write(f"Target Date: {result['target_date']}")
        self.stdout.write(f"Meal Plan ID: {result['meal_plan_id']}")
        self.stdout.write(f"Prep Preference: {result['prep_preference']}")
        
        # Warnings
        warnings = result.get('warnings', [])
        if warnings:
            self.stdout.write(f"\nWarnings:")
            for warning in warnings:
                self.stdout.write(f"  ⚠ {warning}")
        
        # Actions taken
        actions = result.get('actions_taken', [])
        if actions:
            self.stdout.write(f"\nActions Taken:")
            for action in actions:
                self.stdout.write(f"  ✓ {action}")
        else:
            self.stdout.write(f"\nNo actions were taken")
        
        # Overall status
        if result['status'] == 'success':
            if actions:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Instructions sent successfully!")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"\n⚠ No instructions sent - check warnings above")
                )
        
        self.stdout.write("\n" + "="*50) 