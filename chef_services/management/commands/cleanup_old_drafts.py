"""
Management command to clean up old draft service orders.

Draft orders that haven't been completed within 24 hours are considered abandoned
and can be safely deleted to prevent clutter in the orders list.

Usage:
    python manage.py cleanup_old_drafts
    python manage.py cleanup_old_drafts --hours=48  # Custom cutoff
    python manage.py cleanup_old_drafts --dry-run   # Preview without deleting
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chef_services.models import ChefServiceOrder


class Command(BaseCommand):
    help = 'Delete draft service orders older than a specified time (default: 24 hours)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Delete drafts older than this many hours (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        cutoff = timezone.now() - timedelta(hours=hours)
        old_drafts = ChefServiceOrder.objects.filter(
            status='draft',
            created_at__lt=cutoff
        )
        
        count = old_drafts.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No old draft orders to clean up.'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would delete {count} draft order(s) older than {hours} hours:'
            ))
            for order in old_drafts[:10]:  # Show first 10
                self.stdout.write(f'  - Order #{order.id}: {order.offering} (created {order.created_at})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            old_drafts.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {count} draft order(s) older than {hours} hours.'
            ))
