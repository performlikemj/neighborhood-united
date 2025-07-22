from django.core.management.base import BaseCommand, CommandError
from meals.meal_instructions import diagnose_meal_instructions
from datetime import datetime
import json


class Command(BaseCommand):
    help = 'Diagnose meal instruction delivery issues for a specific user'

    def add_arguments(self, parser):
        parser.add_argument('user_email', type=str, help='Email of the user to diagnose')
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
        target_date = None
        
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f"Invalid date format: {options['date']}. Use YYYY-MM-DD")
        
        self.stdout.write(f"Diagnosing meal instructions for: {user_email}")
        if target_date:
            self.stdout.write(f"Target date: {target_date}")
        
        diagnosis = diagnose_meal_instructions(user_email, target_date)
        
        if 'error' in diagnosis:
            raise CommandError(diagnosis['error'])
        
        if options['json']:
            self.stdout.write(json.dumps(diagnosis, indent=2, default=str))
        else:
            self._print_diagnosis(diagnosis)
    
    def _print_diagnosis(self, diagnosis):
        """Print diagnosis in human-readable format"""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(f"DIAGNOSIS REPORT")
        self.stdout.write("="*60)
        
        # User info
        self.stdout.write(f"\nUser: {diagnosis['user_email']}")
        self.stdout.write(f"Target Date: {diagnosis['target_date']} ({diagnosis['target_day']})")
        
        # User settings
        settings = diagnosis['user_settings']
        self.stdout.write(f"\nUser Settings:")
        self.stdout.write(f"  - Email Confirmed: {settings['email_confirmed']}")
        self.stdout.write(f"  - Unsubscribed: {settings['unsubscribed_from_emails']}")
        self.stdout.write(f"  - Timezone: {settings['timezone']}")
        
        # Current time info
        if 'current_time' in diagnosis:
            time_info = diagnosis['current_time']
            self.stdout.write(f"\nTiming:")
            self.stdout.write(f"  - UTC Time: {time_info['utc']}")
            self.stdout.write(f"  - User Local Time: {time_info['user_local']}")
            self.stdout.write(f"  - In 8 PM Window: {time_info['is_8pm_window']}")
        
        # Timezone issues
        if diagnosis['timezone_issues']:
            self.stdout.write(f"\nTimezone Issues:")
            for issue in diagnosis['timezone_issues']:
                self.stdout.write(f"  - {issue}")
        
        # Meal plan status
        meal_plan = diagnosis['meal_plan_status']
        self.stdout.write(f"\nMeal Plan:")
        if meal_plan.get('exists'):
            self.stdout.write(f"  - ID: {meal_plan['meal_plan_id']}")
            self.stdout.write(f"  - Approved: {meal_plan['is_approved']}")
            self.stdout.write(f"  - Prep Preference: {meal_plan['meal_prep_preference']}")
            self.stdout.write(f"  - Has Changes: {meal_plan['has_changes']}")
            self.stdout.write(f"  - Week: {meal_plan['week_start']} to {meal_plan['week_end']}")
            self.stdout.write(f"  - Meals Count: {meal_plan['meals_count']}")
        else:
            self.stdout.write(f"  - Status: NOT FOUND")
            self.stdout.write(f"  - Reason: {meal_plan.get('reason', 'Unknown')}")
        
        # Instruction status
        instruction_status = diagnosis['instruction_status']
        if instruction_status:
            self.stdout.write(f"\nInstructions:")
            
            if 'daily_instructions' in instruction_status:
                self.stdout.write(f"  Daily Instructions:")
                for inst in instruction_status['daily_instructions']:
                    status = "✓" if inst['has_instruction'] else "✗"
                    self.stdout.write(f"    {status} {inst['meal_type']}: {inst['meal_name']}")
            
            if 'bulk_prep' in instruction_status:
                bulk_status = "✓" if instruction_status['bulk_prep']['exists'] else "✗"
                self.stdout.write(f"  {bulk_status} Bulk Prep Instructions")
                
            if 'follow_up' in instruction_status:
                follow_status = "✓" if instruction_status['follow_up']['exists'] else "✗"
                self.stdout.write(f"  {follow_status} Follow-up Instructions for {instruction_status['follow_up']['target_date']}")
        
        # Recommendations
        recommendations = diagnosis['recommendations']
        if recommendations:
            self.stdout.write(f"\nRecommendations:")
            for i, rec in enumerate(recommendations, 1):
                self.stdout.write(f"  {i}. {rec}")
        else:
            self.stdout.write(f"\n✓ No issues found - instructions should be delivered normally")
        
        self.stdout.write("\n" + "="*60) 