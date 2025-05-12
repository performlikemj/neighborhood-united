import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from customer_dashboard.models import UserDailySummary
from custom_auth.models import CustomUser
from meals.email_service import generate_user_summary

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generates a daily summary for a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            'user_id',
            type=int,
            help='ID of the user to generate a summary for',
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force generation even if a summary already exists for today',
        )
        
        parser.add_argument(
            '--date',
            type=str,
            help='Generate summary for a specific date (YYYY-MM-DD), defaults to today',
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        force = options['force']
        date_str = options.get('date')
        
        try:
            user = CustomUser.objects.get(id=user_id)
            self.stdout.write(f"Found user: {user.username}")
            
            # Determine the date to use
            if date_str:
                from datetime import datetime
                try:
                    summary_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    self.stdout.write(f"Using specified date: {summary_date}")
                except ValueError:
                    self.stdout.write(self.style.ERROR(f"Invalid date format: {date_str}. Use YYYY-MM-DD"))
                    return
            else:
                summary_date = timezone.now().date()
                self.stdout.write(f"Using today's date: {summary_date}")
            
            # Check if a summary already exists for this date
            existing = UserDailySummary.objects.filter(
                user=user,
                summary_date=summary_date
            ).first()
            
            if existing and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"A summary already exists for user {user.username} on {summary_date}. "
                        f"Current status: {existing.status}. Use --force to override."
                    )
                )
                return
            
            # Run the summary generation task synchronously
            self.stdout.write(f"Generating summary for user {user.username} on {summary_date}...")
            
            result = generate_user_summary(user_id, summary_date.strftime('%Y-%m-%d'))
            
            self.stdout.write(self.style.SUCCESS(f"Summary generated successfully for {user.username}"))
            
            # Display the summary
            updated_summary = UserDailySummary.objects.get(
                user=user,
                summary_date=summary_date
            )
            
            self.stdout.write("\nSummary content:")
            self.stdout.write("-" * 80)
            self.stdout.write(updated_summary.summary)
            self.stdout.write("-" * 80)
            
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating summary: {str(e)}"))
            logger.error(f"Error generating summary for user {user_id}: {str(e)}", exc_info=True) 