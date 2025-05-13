import re
from django.core.management.base import BaseCommand
from custom_auth.models import Address
from local_chefs.models import PostalCode, ChefPostalCode
from django.db import transaction


class Command(BaseCommand):
    help = 'Normalize postal codes and fill in display fields for existing records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the command without making any changes to the database',
        )

    def normalize_postal_code(self, postal_code):
        """
        Apply consistent normalization to postal codes.
        Remove all non-alphanumeric characters and convert to uppercase.
        """
        if not postal_code:
            return None
        return re.sub(r'[^A-Z0-9]', '', postal_code.upper())

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Start transaction - we'll commit all at once if everything succeeds
        with transaction.atomic():
            # First, update the Address model
            self.stdout.write('Processing addresses...')
            address_updates = 0
            
            for address in Address.objects.all():
                if address.input_postalcode:
                    # If display_postalcode is not set, use the current input_postalcode as the display version
                    if not address.display_postalcode:
                        address.display_postalcode = address.input_postalcode
                        
                    # Normalize the input_postalcode
                    normalized = self.normalize_postal_code(address.input_postalcode)
                    
                    # Only update if there's a change
                    if normalized != address.input_postalcode:
                        self.stdout.write(f"  - Address {address.id}: '{address.input_postalcode}' -> '{normalized}'")
                        address.input_postalcode = normalized
                        
                        if not dry_run:
                            address.save(update_fields=['input_postalcode', 'display_postalcode'])
                        address_updates += 1
            
            # Next, update PostalCode records
            self.stdout.write('Processing postal codes...')
            postal_code_updates = 0
            
            for postal_code in PostalCode.objects.all():
                # If display_code is not set, use the current code as the display version
                if not postal_code.display_code:
                    postal_code.display_code = postal_code.code
                    self.stdout.write(f"  - Setting display_code for PostalCode {postal_code.id} to '{postal_code.code}'")
                    if not dry_run:
                        postal_code.save(update_fields=['display_code'])
                
                normalized = self.normalize_postal_code(postal_code.code)
                
                # Only update if there's a change
                if normalized != postal_code.code:
                    self.stdout.write(f"  - PostalCode {postal_code.id}: '{postal_code.code}' -> '{normalized}'")
                    
                    # In a real scenario, we need to be careful here to avoid conflicts
                    # Check if a normalized version already exists
                    existing = PostalCode.objects.filter(
                        code=normalized, 
                        country=postal_code.country
                    ).first()
                    
                    if existing:
                        self.stdout.write(f"    WARNING: PostalCode conflict. {postal_code.id} would normalize to same as {existing.id}")
                        
                        # If existing has no display_code but we do, transfer it
                        if not existing.display_code and postal_code.display_code:
                            existing.display_code = postal_code.display_code
                            if not dry_run:
                                existing.save(update_fields=['display_code'])
                            self.stdout.write(f"    Updated display_code on {existing.id} to '{postal_code.display_code}'")
                        
                        # Handle chef postal code relationships if needed
                        chef_postal_codes = ChefPostalCode.objects.filter(postal_code=postal_code)
                        for chef_postal_code in chef_postal_codes:
                            # Check if relationship already exists
                            if not ChefPostalCode.objects.filter(
                                chef=chef_postal_code.chef, 
                                postal_code=existing
                            ).exists():
                                self.stdout.write(f"      Moving chef {chef_postal_code.chef.id} to postal code {existing.id}")
                                if not dry_run:
                                    chef_postal_code.postal_code = existing
                                    chef_postal_code.save()
                            else:
                                self.stdout.write(f"      Chef {chef_postal_code.chef.id} already has postal code {existing.id}")
                                if not dry_run:
                                    chef_postal_code.delete()
                        
                        # Delete the duplicate postal code if there are no more relationships
                        if not dry_run:
                            # Check if safe to delete
                            if not ChefPostalCode.objects.filter(postal_code=postal_code).exists():
                                postal_code.delete()
                                self.stdout.write(f"    Deleted duplicate postal code {postal_code.id}")
                    else:
                        # Save the original display before normalizing
                        if not postal_code.display_code:
                            postal_code.display_code = postal_code.code
                            
                        postal_code.code = normalized
                        if not dry_run:
                            postal_code.save(update_fields=['code', 'display_code'])
                        postal_code_updates += 1
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
                # Roll back the transaction
                transaction.set_rollback(True)
            
            self.stdout.write(self.style.SUCCESS(f'Processed {address_updates} addresses and {postal_code_updates} postal codes')) 