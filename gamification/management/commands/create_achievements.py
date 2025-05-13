from django.core.management.base import BaseCommand
from django.db import transaction

from gamification.models import Achievement


class Command(BaseCommand):
    help = 'Initialize default achievements in the gamification system'

    def handle(self, *args, **options):
        self.stdout.write('Creating achievements...')
        
        # Define achievements
        achievements = [
            # Points-based achievements
            {
                'name': 'Beginner',
                'description': 'Earned 100 points',
                'icon': 'fa-medal',
                'points_reward': 50,
                'points_threshold': 100,
                'streak_threshold': None,
                'meals_planned_threshold': None
            },
            {
                'name': 'Intermediate',
                'description': 'Earned 500 points',
                'icon': 'fa-medal',
                'points_reward': 100,
                'points_threshold': 500,
                'streak_threshold': None,
                'meals_planned_threshold': None
            },
            {
                'name': 'Advanced',
                'description': 'Earned 1000 points',
                'icon': 'fa-medal',
                'points_reward': 200,
                'points_threshold': 1000,
                'streak_threshold': None,
                'meals_planned_threshold': None
            },
            {
                'name': 'Expert',
                'description': 'Earned 2500 points',
                'icon': 'fa-crown',
                'points_reward': 300,
                'points_threshold': 2500,
                'streak_threshold': None,
                'meals_planned_threshold': None
            },
            {
                'name': 'Master',
                'description': 'Earned 5000 points',
                'icon': 'fa-crown',
                'points_reward': 500,
                'points_threshold': 5000,
                'streak_threshold': None,
                'meals_planned_threshold': None
            },
            
            # Streak-based achievements
            {
                'name': 'Week Streak',
                'description': 'Maintained a 7-day streak',
                'icon': 'fa-fire',
                'points_reward': 75,
                'points_threshold': None,
                'streak_threshold': 7,
                'meals_planned_threshold': None
            },
            {
                'name': 'Fortnight Streak',
                'description': 'Maintained a 14-day streak',
                'icon': 'fa-fire',
                'points_reward': 150,
                'points_threshold': None,
                'streak_threshold': 14,
                'meals_planned_threshold': None
            },
            {
                'name': 'Month Streak',
                'description': 'Maintained a 30-day streak',
                'icon': 'fa-fire-flame-curved',
                'points_reward': 300,
                'points_threshold': None,
                'streak_threshold': 30,
                'meals_planned_threshold': None
            },
            {
                'name': 'Quarter Streak',
                'description': 'Maintained a 90-day streak',
                'icon': 'fa-fire-flame-curved',
                'points_reward': 500,
                'points_threshold': None,
                'streak_threshold': 90,
                'meals_planned_threshold': None
            },
            {
                'name': 'Half-Year Streak',
                'description': 'Maintained a 180-day streak',
                'icon': 'fa-fire-flame-curved',
                'points_reward': 1000,
                'points_threshold': None,
                'streak_threshold': 180,
                'meals_planned_threshold': None
            },
            
            # Meals planned achievements
            {
                'name': 'First Meal',
                'description': 'Planned your first meal',
                'icon': 'fa-utensils',
                'points_reward': 25,
                'points_threshold': None,
                'streak_threshold': None,
                'meals_planned_threshold': 1
            },
            {
                'name': 'Meal Planner',
                'description': 'Planned 10 meals',
                'icon': 'fa-utensils',
                'points_reward': 50,
                'points_threshold': None,
                'streak_threshold': None,
                'meals_planned_threshold': 10
            },
            {
                'name': 'Culinary Explorer',
                'description': 'Planned 25 meals',
                'icon': 'fa-utensils',
                'points_reward': 100,
                'points_threshold': None,
                'streak_threshold': None,
                'meals_planned_threshold': 25
            },
            {
                'name': 'Meal Maestro',
                'description': 'Planned 50 meals',
                'icon': 'fa-kitchen-set',
                'points_reward': 200,
                'points_threshold': None,
                'streak_threshold': None,
                'meals_planned_threshold': 50
            },
            {
                'name': 'Chef Supreme',
                'description': 'Planned 100 meals',
                'icon': 'fa-kitchen-set',
                'points_reward': 300,
                'points_threshold': None,
                'streak_threshold': None,
                'meals_planned_threshold': 100
            },
        ]
        
        with transaction.atomic():
            # Count existing achievements to check if this is a fresh initialization
            existing_count = Achievement.objects.count()
            
            if existing_count > 0:
                # Achievements already exist, ask for confirmation to overwrite
                self.stdout.write(self.style.WARNING(
                    f'Found {existing_count} existing achievements. Do you want to create new ones? '
                    f'This will not remove existing achievements, but may create duplicates. (y/n)'
                ))
                
                user_input = input().strip().lower()
                if user_input != 'y':
                    self.stdout.write(self.style.SUCCESS('Command aborted. No changes made.'))
                    return
            
            # Create achievements
            created_count = 0
            
            for achievement_data in achievements:
                # Check if achievement with this name already exists
                if not Achievement.objects.filter(name=achievement_data['name']).exists():
                    Achievement.objects.create(**achievement_data)
                    created_count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created {created_count} new achievements. '
                f'Total achievements: {Achievement.objects.count()}'
            )) 