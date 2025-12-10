# Description: This file contains the models for the local_chefs app.
from django.db import models
from django_countries.fields import CountryField
import re


class AdministrativeArea(models.Model):
    """
    Geographic administrative areas (cities, wards, districts, prefectures, states, etc.)
    that group postal codes together for easier service area selection.
    """
    AREA_TYPE_CHOICES = [
        ('country', 'Country'),
        ('state', 'State/Province'),
        ('prefecture', 'Prefecture'),
        ('county', 'County'),
        ('city', 'City'),
        ('ward', 'Ward'),
        ('district', 'District'),
        ('neighborhood', 'Neighborhood'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255, help_text="Display name in English (e.g., 'Shibuya')")
    name_local = models.CharField(max_length=255, blank=True, help_text="Local language name (e.g., '渋谷区')")
    area_type = models.CharField(max_length=20, choices=AREA_TYPE_CHOICES, default='city')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent area (e.g., Shibuya -> Tokyo)"
    )
    country = CountryField(help_text="Country this area belongs to")
    geonames_id = models.BigIntegerField(null=True, blank=True, unique=True, help_text="GeoNames ID for sync")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True, help_text="Cached boundary polygon as GeoJSON")
    postal_code_count = models.PositiveIntegerField(default=0, help_text="Cached count of postal codes in this area")
    
    class Meta:
        verbose_name_plural = "Administrative areas"
        indexes = [
            models.Index(fields=['country', 'area_type']),
            models.Index(fields=['name']),
            models.Index(fields=['parent']),
        ]
        # Allow same name in different parents (e.g., "Springfield" in different states)
        unique_together = [('name', 'parent', 'country', 'area_type')]

    def __str__(self):
        if self.parent:
            return f"{self.name}, {self.parent.name}"
        return f"{self.name}, {self.country.name}"

    @property
    def full_path(self):
        """Returns full hierarchical path like 'Shibuya, Tokyo, Japan'"""
        parts = [self.name]
        current = self.parent
        while current:
            parts.append(current.name)
            current = current.parent
        parts.append(self.country.name)
        return ', '.join(parts)

    def get_all_postal_codes(self):
        """Get all postal codes in this area and its children"""
        from django.db.models import Q
        
        # Get direct postal codes
        postal_codes = set(self.postal_codes.values_list('id', flat=True))
        
        # Recursively get from children
        for child in self.children.all():
            postal_codes.update(child.get_all_postal_codes().values_list('id', flat=True))
        
        return PostalCode.objects.filter(id__in=postal_codes)

    def update_postal_code_count(self):
        """Update the cached postal code count"""
        self.postal_code_count = self.get_all_postal_codes().count()
        self.save(update_fields=['postal_code_count'])


class PostalCode(models.Model):
    code = models.CharField(max_length=15)  # Normalized format (uppercase, no special chars)
    display_code = models.CharField(max_length=20, blank=True, null=True)  # Original format for display
    country = CountryField(default='US')  # Default to US, but can be changed
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geocoded_at = models.DateTimeField(null=True, blank=True)
    # Link to administrative area for area-based selection
    admin_area = models.ForeignKey(
        AdministrativeArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='postal_codes',
        help_text="The city/ward/district this postal code belongs to"
    )
    place_name = models.CharField(max_length=255, blank=True, help_text="Place name from GeoNames")

    class Meta:
        unique_together = ('code', 'country')  # Ensure uniqueness per country

    def __str__(self):
        display = self.display_code or self.code
        return f"{display}, {self.country.name}"

    @staticmethod
    def normalize_code(postal_code):
        """
        Normalize a postal code for storage and lookup.
        Removes all non-alphanumeric characters and converts to uppercase.
        """
        if not postal_code:
            return None
            
        return re.sub(r'[^A-Z0-9]', '', postal_code.upper())
    
    @classmethod
    def get_or_create_normalized(cls, code, country):
        """
        Get or create a PostalCode with normalized code while preserving the original format.
        
        Args:
            code (str): The postal code (can be in any format)
            country: The country code or object
            
        Returns:
            tuple: (postal_code, created) - The PostalCode object and whether it was created
        """
        if not code or not country:
            return None, False
            
        # Store the original format for display
        original_code = code
        
        # Normalize for database storage and lookups
        normalized_code = cls.normalize_code(code)
        
        postal_code, created = cls.objects.get_or_create(
            code=normalized_code,
            country=country,
            defaults={'display_code': original_code}
        )
        
        # If not created but display_code is not set, update it
        if not created and not postal_code.display_code:
            postal_code.display_code = original_code
            postal_code.save(update_fields=['display_code'])
            
        return postal_code, created
    
    def is_served_by_any_chef(self):
        """Check if any chef serves this postal code"""
        return self.chefpostalcode_set.exists()


class ChefPostalCode(models.Model):
    chef = models.ForeignKey('chefs.Chef', on_delete=models.CASCADE)
    postal_code = models.ForeignKey(PostalCode, on_delete=models.CASCADE, related_name='chefpostalcode_set')

    class Meta:
        unique_together = ('chef', 'postal_code')

    def __str__(self):
        return f"{self.chef.user.username} - {self.postal_code}"
        
    @classmethod
    def add_postal_code_for_chef(cls, chef, postal_code, country):
        """
        Add a postal code to a chef's service area, normalizing the code first.
        
        Args:
            chef: Chef object
            postal_code: Postal code string (will be normalized)
            country: Country code or object
            
        Returns:
            ChefPostalCode: The created or existing relationship
        """
        postal_code_obj, _ = PostalCode.get_or_create_normalized(postal_code, country)
        
        if not postal_code_obj:
            return None
            
        chef_postal_code, created = cls.objects.get_or_create(
            chef=chef,
            postal_code=postal_code_obj
        )
        
        return chef_postal_code


class ServiceAreaRequest(models.Model):
    """
    Request from a chef to add new service areas.
    
    Chefs keep their existing approved areas while new requests go through admin review.
    When approved, the requested areas are added to the chef's service areas.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partially_approved', 'Partially Approved'),
    ]
    
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='service_area_requests'
    )
    
    # Requested areas - can request multiple at once
    requested_areas = models.ManyToManyField(
        AdministrativeArea,
        blank=True,
        related_name='area_requests',
        help_text="Administrative areas requested"
    )
    
    # Individual postal codes requested (for manual additions)
    requested_postal_codes = models.ManyToManyField(
        PostalCode,
        blank=True,
        related_name='postal_requests',
        help_text="Individual postal codes requested"
    )
    
    # Track which items were actually approved (for partial approvals)
    approved_areas = models.ManyToManyField(
        AdministrativeArea,
        blank=True,
        related_name='approved_requests',
        help_text="Areas that were approved (subset of requested_areas for partial approval)"
    )
    approved_postal_codes = models.ManyToManyField(
        PostalCode,
        blank=True,
        related_name='approved_postal_requests',
        help_text="Postal codes that were approved (subset of requested for partial approval)"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Chef's note explaining why they want these areas
    chef_notes = models.TextField(
        blank=True,
        help_text="Chef's explanation for why they want to serve these areas"
    )
    
    # Admin review
    admin_notes = models.TextField(
        blank=True,
        help_text="Admin notes about the review decision"
    )
    reviewed_by = models.ForeignKey(
        'custom_auth.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_area_requests'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chef', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        area_count = self.requested_areas.count()
        pc_count = self.requested_postal_codes.count()
        return f"{self.chef.user.username} - {area_count} areas, {pc_count} codes ({self.status})"
    
    @property
    def total_postal_codes_requested(self):
        """Total postal codes this request would add."""
        count = self.requested_postal_codes.count()
        for area in self.requested_areas.all():
            count += area.get_all_postal_codes().count()
        return count
    
    def approve(self, admin_user, notes=''):
        """Approve entire request and add all areas to chef's service areas."""
        from django.utils import timezone
        from django.db import transaction
        
        with transaction.atomic():
            # Add all postal codes from requested areas
            for area in self.requested_areas.all():
                self.approved_areas.add(area)
                for postal_code in area.get_all_postal_codes():
                    ChefPostalCode.objects.get_or_create(
                        chef=self.chef,
                        postal_code=postal_code
                    )
            
            # Add individual postal codes
            for postal_code in self.requested_postal_codes.all():
                self.approved_postal_codes.add(postal_code)
                ChefPostalCode.objects.get_or_create(
                    chef=self.chef,
                    postal_code=postal_code
                )
            
            self.status = 'approved'
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.admin_notes = notes
            self.save()
    
    def partially_approve(self, admin_user, area_ids=None, postal_code_ids=None, notes=''):
        """
        Partially approve request - only approve selected areas/postal codes.
        
        Args:
            admin_user: The admin user performing the approval
            area_ids: List of AdministrativeArea IDs to approve (from requested_areas)
            postal_code_ids: List of PostalCode IDs to approve (from requested_postal_codes)
            notes: Admin notes about the partial approval
        """
        from django.utils import timezone
        from django.db import transaction
        
        area_ids = area_ids or []
        postal_code_ids = postal_code_ids or []
        
        with transaction.atomic():
            # Track what was approved and add to chef's service areas
            approved_area_count = 0
            approved_code_count = 0
            
            # Process approved areas
            if area_ids:
                areas_to_approve = self.requested_areas.filter(id__in=area_ids)
                for area in areas_to_approve:
                    self.approved_areas.add(area)
                    approved_area_count += 1
                    for postal_code in area.get_all_postal_codes():
                        ChefPostalCode.objects.get_or_create(
                            chef=self.chef,
                            postal_code=postal_code
                        )
                        approved_code_count += 1
            
            # Process approved individual postal codes
            if postal_code_ids:
                codes_to_approve = self.requested_postal_codes.filter(id__in=postal_code_ids)
                for postal_code in codes_to_approve:
                    self.approved_postal_codes.add(postal_code)
                    ChefPostalCode.objects.get_or_create(
                        chef=self.chef,
                        postal_code=postal_code
                    )
                    approved_code_count += 1
            
            self.status = 'partially_approved'
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.admin_notes = notes
            self.save()
            
            return approved_area_count, approved_code_count
    
    def reject(self, admin_user, notes=''):
        """Reject the request."""
        from django.utils import timezone
        
        self.status = 'rejected'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.save()
    
    @property
    def rejected_areas(self):
        """Get areas that were requested but not approved (for partial approvals)."""
        if self.status != 'partially_approved':
            return self.requested_areas.none()
        approved_ids = self.approved_areas.values_list('id', flat=True)
        return self.requested_areas.exclude(id__in=approved_ids)
    
    @property
    def rejected_postal_codes(self):
        """Get postal codes that were requested but not approved (for partial approvals)."""
        if self.status != 'partially_approved':
            return self.requested_postal_codes.none()
        approved_ids = self.approved_postal_codes.values_list('id', flat=True)
        return self.requested_postal_codes.exclude(id__in=approved_ids)
    
    @property
    def approval_summary(self):
        """Get a summary of what was approved vs rejected."""
        if self.status == 'approved':
            return {
                'approved_areas': self.requested_areas.count(),
                'approved_codes': self.total_postal_codes_requested,
                'rejected_areas': 0,
                'rejected_codes': 0,
            }
        elif self.status == 'partially_approved':
            return {
                'approved_areas': self.approved_areas.count(),
                'approved_codes': sum(a.get_all_postal_codes().count() for a in self.approved_areas.all()) + self.approved_postal_codes.count(),
                'rejected_areas': self.rejected_areas.count(),
                'rejected_codes': sum(a.get_all_postal_codes().count() for a in self.rejected_areas) + self.rejected_postal_codes.count(),
            }
        elif self.status == 'rejected':
            return {
                'approved_areas': 0,
                'approved_codes': 0,
                'rejected_areas': self.requested_areas.count(),
                'rejected_codes': self.total_postal_codes_requested,
            }
        return None
    
    @classmethod
    def has_pending_request(cls, chef):
        """Check if chef has any pending requests."""
        return cls.objects.filter(chef=chef, status='pending').exists()
    
    @classmethod
    def get_pending_for_chef(cls, chef):
        """Get all pending requests for a chef."""
        return cls.objects.filter(chef=chef, status='pending')
