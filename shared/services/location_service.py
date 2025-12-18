"""
LocationService - Single source of truth for all postal code operations.

This service centralizes postal code handling to eliminate duplicate logic
and provide consistent behavior across the application.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_auth.models import CustomUser
    from local_chefs.models import PostalCode


@dataclass
class UserLocation:
    """Represents a user's location information."""
    normalized_postal: str | None
    country: str | None
    display_postal: str | None
    
    @property
    def is_complete(self) -> bool:
        """Check if location has both postal code and country."""
        return bool(self.normalized_postal and self.country)


class LocationService:
    """
    Single source of truth for all postal code operations.
    
    This service provides:
    - Postal code normalization (delegating to PostalCode.normalize_code)
    - User location extraction
    - PostalCode record management
    - Chef coverage checks
    - Country-specific postal code validation
    """
    
    # Country-specific postal code validation rules
    POSTAL_CODE_RULES = {
        'US': {
            'pattern': lambda code: len(code) in (5, 9) and code.isdigit(),
            'message': 'US postal codes must be 5 digits or 9 digits (ZIP+4)',
        },
        'CA': {
            'pattern': lambda code: (
                len(code) == 6 and
                code[0::2].isalpha() and
                code[1::2].isdigit()
            ),
            'message': 'Canadian postal codes must be in the format A1A 1A1',
        },
        'JP': {
            'pattern': lambda code: len(code) == 7 and code.isdigit(),
            'message': 'Japanese postal codes must be 7 digits',
        },
        'UK': {
            'pattern': lambda code: 5 <= len(code) <= 7,  # Basic UK postcode validation
            'message': 'UK postal codes must be 5-7 characters',
        },
        'GB': {  # UK alternative code
            'pattern': lambda code: 5 <= len(code) <= 7,
            'message': 'UK postal codes must be 5-7 characters',
        },
    }
    
    @staticmethod
    def normalize(code: str | None) -> str | None:
        """
        Normalize a postal code for storage and lookup.
        
        Removes all non-alphanumeric characters and converts to uppercase.
        Delegates to PostalCode.normalize_code as the canonical implementation.
        
        Args:
            code: The postal code to normalize (can be None)
            
        Returns:
            Normalized postal code string or None if input is empty/None
        """
        if not code:
            return None
        
        # Import here to avoid circular imports
        from local_chefs.models import PostalCode
        return PostalCode.normalize_code(code)
    
    @staticmethod
    def get_user_location(user: CustomUser | None) -> UserLocation:
        """
        Extract location information from a user's address.
        
        Args:
            user: The user object (can be None or anonymous)
            
        Returns:
            UserLocation dataclass with normalized_postal, country, and display_postal
        """
        if not user or not hasattr(user, 'address'):
            return UserLocation(
                normalized_postal=None,
                country=None,
                display_postal=None
            )
        
        address = getattr(user, 'address', None)
        if not address:
            return UserLocation(
                normalized_postal=None,
                country=None,
                display_postal=None
            )
        
        # Get normalized postal code (stored in input_postalcode field)
        # Note: After migration, this will be normalized_postalcode
        normalized_postal = getattr(address, 'normalized_postalcode', None)
        if normalized_postal is None:
            # Fallback for pre-migration code
            normalized_postal = getattr(address, 'input_postalcode', None)
        
        # Get country
        country = getattr(address, 'country', None)
        country_str = str(country) if country else None
        
        # Get display postal (original user input)
        # Note: After migration, this will be original_postalcode
        display_postal = getattr(address, 'original_postalcode', None)
        if display_postal is None:
            # Fallback for pre-migration code
            display_postal = getattr(address, 'display_postalcode', None)
        
        # If no display postal, use normalized
        if not display_postal:
            display_postal = normalized_postal
        
        return UserLocation(
            normalized_postal=normalized_postal,
            country=country_str,
            display_postal=display_postal
        )
    
    @classmethod
    def get_or_create_postal_code(
        cls,
        code: str,
        country: str,
        display_code: str | None = None
    ) -> PostalCode | None:
        """
        Get or create a PostalCode record with normalization.
        
        Args:
            code: The postal code (will be normalized)
            country: The country code (e.g., 'US', 'CA')
            display_code: Optional original format for display
            
        Returns:
            PostalCode object or None if inputs are invalid
        """
        if not code or not country:
            return None
        
        from local_chefs.models import PostalCode
        
        normalized = cls.normalize(code)
        if not normalized:
            return None
        
        postal_code, created = PostalCode.objects.get_or_create(
            code=normalized,
            country=country,
            defaults={'display_code': display_code or code}
        )
        
        # Update display_code if not set
        if not created and not postal_code.display_code and display_code:
            postal_code.display_code = display_code
            postal_code.save(update_fields=['display_code'])
        
        return postal_code
    
    @classmethod
    def get_postal_code(cls, code: str, country: str) -> PostalCode | None:
        """
        Get a PostalCode record by normalized code and country.
        
        Args:
            code: The postal code (will be normalized)
            country: The country code
            
        Returns:
            PostalCode object or None if not found
        """
        if not code or not country:
            return None
        
        from local_chefs.models import PostalCode
        
        normalized = cls.normalize(code)
        if not normalized:
            return None
        
        try:
            return PostalCode.objects.get(code=normalized, country=country)
        except PostalCode.DoesNotExist:
            return None
    
    @classmethod
    def has_chef_coverage(cls, user: CustomUser | None) -> bool:
        """
        Check if any verified chef serves the user's area.
        
        Args:
            user: The user to check coverage for
            
        Returns:
            True if at least one verified chef serves the user's postal code
        """
        location = cls.get_user_location(user)
        if not location.is_complete:
            return False
        
        return cls.has_chef_coverage_for_area(
            location.normalized_postal,
            location.country
        )
    
    @classmethod
    def has_chef_coverage_for_area(
        cls,
        postal_code: str,
        country: str
    ) -> bool:
        """
        Check if any verified chef serves a specific area.
        
        Args:
            postal_code: The postal code (will be normalized)
            country: The country code
            
        Returns:
            True if at least one verified chef serves this area
        """
        if not postal_code or not country:
            return False
        
        from local_chefs.models import ChefPostalCode
        
        normalized = cls.normalize(postal_code)
        if not normalized:
            return False
        
        return ChefPostalCode.objects.filter(
            postal_code__code=normalized,
            postal_code__country=country,
            chef__is_verified=True
        ).exists()
    
    @classmethod
    def get_verified_chef_count(cls, postal_code: str, country: str) -> int:
        """
        Get count of verified chefs serving an area.
        
        Args:
            postal_code: The postal code (will be normalized)
            country: The country code
            
        Returns:
            Number of verified chefs serving this area
        """
        if not postal_code or not country:
            return 0
        
        from local_chefs.models import ChefPostalCode
        
        normalized = cls.normalize(postal_code)
        if not normalized:
            return 0
        
        return ChefPostalCode.objects.filter(
            postal_code__code=normalized,
            postal_code__country=country,
            chef__is_verified=True
        ).count()
    
    @classmethod
    def validate_postal_code(
        cls,
        code: str,
        country: str
    ) -> tuple[bool, str | None]:
        """
        Validate postal code format for a given country.
        
        Args:
            code: The postal code to validate (will be normalized first)
            country: The country code
            
        Returns:
            Tuple of (is_valid, error_message)
            error_message is None if valid
        """
        if not code:
            return False, 'Postal code is required'
        
        if not country:
            return False, 'Country is required'
        
        normalized = cls.normalize(code)
        if not normalized:
            return False, 'Invalid postal code format'
        
        # Get country-specific rules
        country_str = str(country).upper()
        rules = cls.POSTAL_CODE_RULES.get(country_str)
        
        if rules:
            pattern_fn = rules['pattern']
            if not pattern_fn(normalized):
                return False, rules['message']
        
        # If no specific rules, accept any alphanumeric code
        return True, None
    
    @classmethod
    def format_location_string(cls, user: CustomUser | None) -> str:
        """
        Format a user's location as a human-readable string.
        
        Args:
            user: The user object
            
        Returns:
            Formatted location string or 'Location not provided'
        """
        location = cls.get_user_location(user)
        
        if not location.is_complete:
            return 'Location not provided'
        
        postal = location.display_postal or location.normalized_postal
        return f"{postal}, {location.country}"
    
    @classmethod
    def user_can_access_chef_features(cls, user: CustomUser | None) -> dict:
        """
        Comprehensive check for user's chef feature access.
        
        Args:
            user: The user to check
            
        Returns:
            Dict with access info:
            {
                'has_access': bool,
                'reason': str | None,
                'location': UserLocation,
                'chef_count': int
            }
        """
        location = cls.get_user_location(user)
        
        if not user:
            return {
                'has_access': False,
                'reason': 'not_authenticated',
                'location': location,
                'chef_count': 0
            }
        
        if not location.normalized_postal:
            return {
                'has_access': False,
                'reason': 'no_postal_code',
                'location': location,
                'chef_count': 0
            }
        
        if not location.country:
            return {
                'has_access': False,
                'reason': 'no_country',
                'location': location,
                'chef_count': 0
            }
        
        chef_count = cls.get_verified_chef_count(
            location.normalized_postal,
            location.country
        )
        
        if chef_count == 0:
            return {
                'has_access': False,
                'reason': 'no_chefs_in_area',
                'location': location,
                'chef_count': 0
            }
        
        return {
            'has_access': True,
            'reason': None,
            'location': location,
            'chef_count': chef_count
        }







