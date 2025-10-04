from django.core.management.base import BaseCommand
from chef_services.tasks import sync_pending_service_tiers


class Command(BaseCommand):
    help = "Provision Stripe Products/Prices for pending chef service tiers"

    def handle(self, *args, **options):
        result = sync_pending_service_tiers()
        self.stdout.write(self.style.SUCCESS(f"Sync complete: {result}"))

