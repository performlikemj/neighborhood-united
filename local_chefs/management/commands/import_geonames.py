"""
Management command to import postal code and administrative area data from GeoNames.

GeoNames provides free postal code data for most countries at:
https://download.geonames.org/export/zip/

File format (tab-separated):
- country code
- postal code
- place name
- admin name1 (state/prefecture)
- admin code1
- admin name2 (county/city)
- admin code2
- admin name3 (ward/district)
- admin code3
- latitude
- longitude
- accuracy

Usage:
    python manage.py import_geonames JP US  # Import Japan and US
    python manage.py import_geonames --all  # Import all available countries
    python manage.py import_geonames JP --clear  # Clear JP data before import
"""

import os
import io
import zipfile
import tempfile
from collections import defaultdict
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
import requests

from local_chefs.models import PostalCode, AdministrativeArea


# GeoNames column indices
COL_COUNTRY = 0
COL_POSTAL_CODE = 1
COL_PLACE_NAME = 2
COL_ADMIN1_NAME = 3  # State/Prefecture
COL_ADMIN1_CODE = 4
COL_ADMIN2_NAME = 5  # County/City
COL_ADMIN2_CODE = 6
COL_ADMIN3_NAME = 7  # Ward/District
COL_ADMIN3_CODE = 8
COL_LATITUDE = 9
COL_LONGITUDE = 10
COL_ACCURACY = 11

GEONAMES_BASE_URL = "https://download.geonames.org/export/zip/"

# Area type mappings per country for proper hierarchy
COUNTRY_AREA_CONFIG = {
    'JP': {
        'admin1_type': 'prefecture',
        'admin2_type': 'city',
        'admin3_type': 'ward',
    },
    'US': {
        'admin1_type': 'state',
        'admin2_type': 'county',
        'admin3_type': 'city',
    },
    # Default for other countries
    'DEFAULT': {
        'admin1_type': 'state',
        'admin2_type': 'city',
        'admin3_type': 'district',
    }
}


class Command(BaseCommand):
    help = 'Import postal codes and administrative areas from GeoNames data'

    def add_arguments(self, parser):
        parser.add_argument(
            'countries',
            nargs='*',
            help='Country codes to import (e.g., JP US GB). Leave empty with --all to import all.'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Import all available country data (downloads allCountries.zip)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data for specified countries before import'
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default=None,
            help='Directory containing pre-downloaded GeoNames zip files'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5000,
            help='Batch size for database operations (default: 5000)'
        )

    def handle(self, *args, **options):
        countries = options['countries']
        import_all = options['all']
        clear_existing = options['clear']
        data_dir = options['data_dir']
        batch_size = options['batch_size']

        if not countries and not import_all:
            raise CommandError('Please specify country codes or use --all')

        if import_all:
            self.stdout.write('Importing all countries from allCountries.zip...')
            self.import_all_countries(data_dir, batch_size, clear_existing)
        else:
            for country_code in countries:
                country_code = country_code.upper()
                self.stdout.write(f'Importing {country_code}...')
                try:
                    self.import_country(country_code, data_dir, batch_size, clear_existing)
                    self.stdout.write(self.style.SUCCESS(f'Successfully imported {country_code}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to import {country_code}: {e}'))

    def get_zip_file(self, country_code, data_dir=None):
        """Download or load GeoNames zip file for a country."""
        filename = f"{country_code}.zip"
        
        # Check local directory first
        if data_dir:
            local_path = os.path.join(data_dir, filename)
            if os.path.exists(local_path):
                self.stdout.write(f'  Using local file: {local_path}')
                return open(local_path, 'rb')
        
        # Download from GeoNames
        url = f"{GEONAMES_BASE_URL}{filename}"
        self.stdout.write(f'  Downloading {url}...')
        
        response = requests.get(url, stream=True, timeout=120)
        if response.status_code == 404:
            raise CommandError(f'GeoNames data not found for country: {country_code}')
        response.raise_for_status()
        
        return io.BytesIO(response.content)

    def parse_geonames_line(self, line, country_code):
        """Parse a single line from GeoNames data."""
        parts = line.strip().split('\t')
        if len(parts) < 10:
            return None
            
        try:
            return {
                'country': parts[COL_COUNTRY],
                'postal_code': parts[COL_POSTAL_CODE],
                'place_name': parts[COL_PLACE_NAME],
                'admin1_name': parts[COL_ADMIN1_NAME] if len(parts) > COL_ADMIN1_NAME else '',
                'admin1_code': parts[COL_ADMIN1_CODE] if len(parts) > COL_ADMIN1_CODE else '',
                'admin2_name': parts[COL_ADMIN2_NAME] if len(parts) > COL_ADMIN2_NAME else '',
                'admin2_code': parts[COL_ADMIN2_CODE] if len(parts) > COL_ADMIN2_CODE else '',
                'admin3_name': parts[COL_ADMIN3_NAME] if len(parts) > COL_ADMIN3_NAME else '',
                'admin3_code': parts[COL_ADMIN3_CODE] if len(parts) > COL_ADMIN3_CODE else '',
                'latitude': Decimal(parts[COL_LATITUDE]) if parts[COL_LATITUDE] else None,
                'longitude': Decimal(parts[COL_LONGITUDE]) if parts[COL_LONGITUDE] else None,
            }
        except (ValueError, IndexError) as e:
            self.stdout.write(self.style.WARNING(f'  Skipping malformed line: {e}'))
            return None

    def get_area_config(self, country_code):
        """Get area type configuration for a country."""
        return COUNTRY_AREA_CONFIG.get(country_code, COUNTRY_AREA_CONFIG['DEFAULT'])

    def import_country(self, country_code, data_dir=None, batch_size=5000, clear_existing=False):
        """Import postal codes for a single country."""
        zip_file = self.get_zip_file(country_code, data_dir)
        
        try:
            with zipfile.ZipFile(zip_file) as zf:
                # Find the main data file (usually {country_code}.txt)
                txt_files = [f for f in zf.namelist() if f.endswith('.txt') and not f.startswith('readme')]
                if not txt_files:
                    raise CommandError(f'No data file found in {country_code}.zip')
                
                data_file = txt_files[0]
                self.stdout.write(f'  Reading {data_file}...')
                
                with zf.open(data_file) as f:
                    content = f.read().decode('utf-8')
                    lines = content.strip().split('\n')
                    
                    self.process_lines(lines, country_code, batch_size, clear_existing)
        finally:
            if hasattr(zip_file, 'close'):
                zip_file.close()

    def import_all_countries(self, data_dir=None, batch_size=5000, clear_existing=False):
        """Import all countries from allCountries.zip."""
        filename = "allCountries.zip"
        
        # Check local directory first
        if data_dir:
            local_path = os.path.join(data_dir, filename)
            if os.path.exists(local_path):
                self.stdout.write(f'Using local file: {local_path}')
                zip_content = open(local_path, 'rb')
            else:
                zip_content = None
        else:
            zip_content = None
            
        if not zip_content:
            url = f"{GEONAMES_BASE_URL}{filename}"
            self.stdout.write(f'Downloading {url} (this may take a while)...')
            response = requests.get(url, stream=True, timeout=600)
            response.raise_for_status()
            zip_content = io.BytesIO(response.content)
        
        try:
            with zipfile.ZipFile(zip_content) as zf:
                data_file = 'allCountries.txt'
                self.stdout.write(f'Reading {data_file}...')
                
                with zf.open(data_file) as f:
                    content = f.read().decode('utf-8')
                    lines = content.strip().split('\n')
                    
                    # Group by country for batch processing
                    by_country = defaultdict(list)
                    for line in lines:
                        parts = line.split('\t')
                        if len(parts) > 0:
                            by_country[parts[0]].append(line)
                    
                    for country_code, country_lines in by_country.items():
                        self.stdout.write(f'Processing {country_code} ({len(country_lines)} records)...')
                        self.process_lines(country_lines, country_code, batch_size, clear_existing)
        finally:
            if hasattr(zip_content, 'close'):
                zip_content.close()

    @transaction.atomic
    def process_lines(self, lines, country_code, batch_size, clear_existing):
        """Process lines and create database records."""
        area_config = self.get_area_config(country_code)
        
        # Clear existing data if requested
        if clear_existing:
            self.stdout.write(f'  Clearing existing data for {country_code}...')
            PostalCode.objects.filter(country=country_code).delete()
            AdministrativeArea.objects.filter(country=country_code).delete()
        
        # Parse all lines first
        records = []
        for line in lines:
            record = self.parse_geonames_line(line, country_code)
            if record and record['country'] == country_code:
                records.append(record)
        
        self.stdout.write(f'  Parsed {len(records)} records')
        
        # Build administrative area hierarchy
        # Cache: (country, admin_level, name, parent_id) -> AdministrativeArea
        area_cache = {}
        
        # Track unique areas at each level
        admin1_areas = {}  # admin1_name -> area
        admin2_areas = {}  # (admin1_name, admin2_name) -> area
        admin3_areas = {}  # (admin1_name, admin2_name, admin3_name) -> area
        
        # First pass: collect unique administrative areas
        for record in records:
            admin1 = record['admin1_name'].strip()
            admin2 = record['admin2_name'].strip()
            admin3 = record['admin3_name'].strip()
            
            if admin1 and admin1 not in admin1_areas:
                admin1_areas[admin1] = {
                    'name': admin1,
                    'lat': record['latitude'],
                    'lon': record['longitude']
                }
            
            if admin1 and admin2:
                key = (admin1, admin2)
                if key not in admin2_areas:
                    admin2_areas[key] = {
                        'name': admin2,
                        'parent_name': admin1,
                        'lat': record['latitude'],
                        'lon': record['longitude']
                    }
            
            if admin1 and admin2 and admin3:
                key = (admin1, admin2, admin3)
                if key not in admin3_areas:
                    admin3_areas[key] = {
                        'name': admin3,
                        'parent1_name': admin1,
                        'parent2_name': admin2,
                        'lat': record['latitude'],
                        'lon': record['longitude']
                    }
        
        self.stdout.write(f'  Creating {len(admin1_areas)} level-1 areas ({area_config["admin1_type"]})...')
        
        # Create admin level 1 areas (states/prefectures)
        admin1_objs = {}
        for name, data in admin1_areas.items():
            area, created = AdministrativeArea.objects.update_or_create(
                name=name,
                country=country_code,
                area_type=area_config['admin1_type'],
                parent=None,
                defaults={
                    'latitude': data['lat'],
                    'longitude': data['lon'],
                }
            )
            admin1_objs[name] = area
        
        self.stdout.write(f'  Creating {len(admin2_areas)} level-2 areas ({area_config["admin2_type"]})...')
        
        # Create admin level 2 areas (cities/counties)
        admin2_objs = {}
        for (parent_name, name), data in admin2_areas.items():
            parent = admin1_objs.get(parent_name)
            area, created = AdministrativeArea.objects.update_or_create(
                name=name,
                country=country_code,
                area_type=area_config['admin2_type'],
                parent=parent,
                defaults={
                    'latitude': data['lat'],
                    'longitude': data['lon'],
                }
            )
            admin2_objs[(parent_name, name)] = area
        
        self.stdout.write(f'  Creating {len(admin3_areas)} level-3 areas ({area_config["admin3_type"]})...')
        
        # Create admin level 3 areas (wards/districts)
        admin3_objs = {}
        for (p1, p2, name), data in admin3_areas.items():
            parent = admin2_objs.get((p1, p2))
            area, created = AdministrativeArea.objects.update_or_create(
                name=name,
                country=country_code,
                area_type=area_config['admin3_type'],
                parent=parent,
                defaults={
                    'latitude': data['lat'],
                    'longitude': data['lon'],
                }
            )
            admin3_objs[(p1, p2, name)] = area
        
        # Now create postal codes with area links
        self.stdout.write(f'  Creating {len(records)} postal codes...')
        
        postal_codes_to_create = []
        postal_codes_to_update = []
        existing_codes = set(
            PostalCode.objects.filter(country=country_code)
            .values_list('code', flat=True)
        )
        
        for record in records:
            normalized = PostalCode.normalize_code(record['postal_code'])
            admin1 = record['admin1_name'].strip()
            admin2 = record['admin2_name'].strip()
            admin3 = record['admin3_name'].strip()
            
            # Find the most specific admin area
            admin_area = None
            if admin1 and admin2 and admin3:
                admin_area = admin3_objs.get((admin1, admin2, admin3))
            if not admin_area and admin1 and admin2:
                admin_area = admin2_objs.get((admin1, admin2))
            if not admin_area and admin1:
                admin_area = admin1_objs.get(admin1)
            
            if normalized in existing_codes:
                # Update existing
                postal_codes_to_update.append({
                    'code': normalized,
                    'display_code': record['postal_code'],
                    'latitude': record['latitude'],
                    'longitude': record['longitude'],
                    'place_name': record['place_name'],
                    'admin_area': admin_area,
                })
            else:
                postal_codes_to_create.append(PostalCode(
                    code=normalized,
                    display_code=record['postal_code'],
                    country=country_code,
                    latitude=record['latitude'],
                    longitude=record['longitude'],
                    place_name=record['place_name'],
                    admin_area=admin_area,
                    geocoded_at=timezone.now(),
                ))
        
        # Bulk create new postal codes
        if postal_codes_to_create:
            self.stdout.write(f'  Bulk creating {len(postal_codes_to_create)} new postal codes...')
            for i in range(0, len(postal_codes_to_create), batch_size):
                batch = postal_codes_to_create[i:i + batch_size]
                PostalCode.objects.bulk_create(batch, ignore_conflicts=True)
                self.stdout.write(f'    Created batch {i // batch_size + 1}')
        
        # Bulk update existing postal codes
        if postal_codes_to_update:
            self.stdout.write(f'  Updating {len(postal_codes_to_update)} existing postal codes...')
            for i in range(0, len(postal_codes_to_update), batch_size):
                batch = postal_codes_to_update[i:i + batch_size]
                for item in batch:
                    PostalCode.objects.filter(
                        code=item['code'],
                        country=country_code
                    ).update(
                        display_code=item['display_code'],
                        latitude=item['latitude'],
                        longitude=item['longitude'],
                        place_name=item['place_name'],
                        admin_area=item['admin_area'],
                    )
        
        # Update postal code counts on areas
        self.stdout.write('  Updating postal code counts...')
        for area in AdministrativeArea.objects.filter(country=country_code):
            count = area.postal_codes.count()
            if count != area.postal_code_count:
                area.postal_code_count = count
                area.save(update_fields=['postal_code_count'])
        
        self.stdout.write(self.style.SUCCESS(
            f'  Done! Created {len(admin1_objs)} {area_config["admin1_type"]}s, '
            f'{len(admin2_objs)} {area_config["admin2_type"]}s, '
            f'{len(admin3_objs)} {area_config["admin3_type"]}s, '
            f'and {len(postal_codes_to_create)} postal codes.'
        ))





