import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from customer_dashboard.models import UserSummary, UserDailySummary
from custom_auth.models import CustomUser

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates data from the legacy UserSummary model to the new UserDailySummary model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry mode without making any changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no changes will be made'))
        
        user_summaries = UserSummary.objects.all()
        count = user_summaries.count()
        self.stdout.write(f'Found {count} UserSummary records to migrate')
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for summary in user_summaries:
            user = summary.user
            try:
                # Use the updated_at date as the summary_date
                if summary.updated_at:
                    summary_date = summary.updated_at.date()
                else:
                    # If no updated_at, use today's date
                    summary_date = timezone.now().date()
                
                # Check if a UserDailySummary already exists for this user and date
                existing = UserDailySummary.objects.filter(
                    user=user,
                    summary_date=summary_date
                ).first()
                
                if existing:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping UserSummary for user {user.username}: '
                            f'UserDailySummary already exists for {summary_date}'
                        )
                    )
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    # Create the new UserDailySummary
                    UserDailySummary.objects.create(
                        user=user,
                        summary_date=summary_date,
                        status=summary.status,
                        summary=summary.summary,
                        # No data_hash since we didn't have it in the old model
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{"Would migrate" if dry_run else "Migrated"} UserSummary for user {user.username} '
                        f'to UserDailySummary on {summary_date}'
                    )
                )
                migrated_count += 1
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error migrating UserSummary for user {user.username}: {str(e)}'
                    )
                )
                logger.error(f'Error migrating UserSummary for user {user.id}: {str(e)}', exc_info=True)
                error_count += 1
        
        # Final summary
        self.stdout.write('\n' + '=' * 80)
        action = "Would migrate" if dry_run else "Migrated"
        self.stdout.write(self.style.SUCCESS(f'{action} {migrated_count} UserSummary records'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped_count} records (already existed)'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Encountered {error_count} errors'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run. Run without --dry-run to apply changes.')) 