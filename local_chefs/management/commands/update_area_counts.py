"""
Management command to update postal code counts for administrative areas.

This recalculates the postal_code_count field to include postal codes from
all child areas, not just direct postal codes.

Usage:
    python manage.py update_area_counts           # Update all countries
    python manage.py update_area_counts JP US     # Update specific countries
"""

from django.core.management.base import BaseCommand
from local_chefs.models import AdministrativeArea


class Command(BaseCommand):
    help = 'Update postal code counts for administrative areas (including child areas)'

    def add_arguments(self, parser):
        parser.add_argument(
            'countries',
            nargs='*',
            help='Country codes to update (e.g., JP US). Leave empty to update all.'
        )

    def handle(self, *args, **options):
        countries = options['countries']
        
        if countries:
            countries = [c.upper() for c in countries]
            qs = AdministrativeArea.objects.filter(country__in=countries)
            self.stdout.write(f'Updating postal code counts for: {", ".join(countries)}')
        else:
            qs = AdministrativeArea.objects.all()
            self.stdout.write('Updating postal code counts for all countries...')
        
        # Get all areas and organize by hierarchy
        areas = list(qs.select_related('parent'))
        
        if not areas:
            self.stdout.write(self.style.WARNING('No areas found to update.'))
            return
        
        # Find areas that have children
        area_ids_with_children = set(
            AdministrativeArea.objects.filter(
                parent__in=qs
            ).values_list('parent_id', flat=True)
        )
        
        # Separate leaf and parent areas
        leaf_areas = [a for a in areas if a.id not in area_ids_with_children]
        parent_areas = [a for a in areas if a.id in area_ids_with_children]
        
        # Further separate level-2 (with parent) and level-1 (no parent)
        level2_areas = [a for a in parent_areas if a.parent is not None]
        level1_areas = [a for a in parent_areas if a.parent is None]
        
        updated_count = 0
        
        # Process leaf areas first (direct counts only)
        self.stdout.write(f'  Updating {len(leaf_areas)} leaf areas...')
        for area in leaf_areas:
            count = area.postal_codes.count()
            if count != area.postal_code_count:
                area.postal_code_count = count
                area.save(update_fields=['postal_code_count'])
                updated_count += 1
        
        # Process level-2 parent areas (cities with wards)
        self.stdout.write(f'  Updating {len(level2_areas)} level-2 areas...')
        for area in level2_areas:
            count = area.get_all_postal_codes().count()
            if count != area.postal_code_count:
                area.postal_code_count = count
                area.save(update_fields=['postal_code_count'])
                updated_count += 1
        
        # Process level-1 parent areas (prefectures/states)
        self.stdout.write(f'  Updating {len(level1_areas)} level-1 areas...')
        for area in level1_areas:
            count = area.get_all_postal_codes().count()
            if count != area.postal_code_count:
                area.postal_code_count = count
                area.save(update_fields=['postal_code_count'])
                updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Done! Updated {updated_count} of {len(areas)} areas.'
        ))
