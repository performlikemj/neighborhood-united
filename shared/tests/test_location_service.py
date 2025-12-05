"""
Tests for LocationService - the centralized postal code handling service.
"""
from decimal import Decimal
from django.test import TestCase

from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from local_chefs.models import PostalCode, ChefPostalCode
from shared.services.location_service import LocationService, UserLocation


class LocationServiceNormalizationTests(TestCase):
    """Test postal code normalization."""
    
    def test_normalize_basic(self):
        """Test basic normalization."""
        self.assertEqual(LocationService.normalize('90210'), '90210')
        self.assertEqual(LocationService.normalize('90210-1234'), '902101234')
        
    def test_normalize_case_insensitive(self):
        """Test that normalization converts to uppercase."""
        self.assertEqual(LocationService.normalize('a1a 1a1'), 'A1A1A1')
        self.assertEqual(LocationService.normalize('ABC123'), 'ABC123')
        
    def test_normalize_removes_special_chars(self):
        """Test that normalization removes spaces, dashes, etc."""
        self.assertEqual(LocationService.normalize('A1A 1A1'), 'A1A1A1')
        self.assertEqual(LocationService.normalize('90210-1234'), '902101234')
        self.assertEqual(LocationService.normalize('123-456-789'), '123456789')
        
    def test_normalize_none_or_empty(self):
        """Test normalization of empty/None values."""
        self.assertIsNone(LocationService.normalize(None))
        self.assertIsNone(LocationService.normalize(''))


class LocationServiceValidationTests(TestCase):
    """Test postal code validation."""
    
    def test_validate_us_postal_code_valid(self):
        """Test valid US postal codes."""
        is_valid, error = LocationService.validate_postal_code('90210', 'US')
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # ZIP+4 format
        is_valid, error = LocationService.validate_postal_code('90210-1234', 'US')
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
    def test_validate_us_postal_code_invalid(self):
        """Test invalid US postal codes."""
        # Too short
        is_valid, error = LocationService.validate_postal_code('9021', 'US')
        self.assertFalse(is_valid)
        self.assertIn('5 digits', error)
        
        # Too long (not 5 or 9)
        is_valid, error = LocationService.validate_postal_code('902100', 'US')
        self.assertFalse(is_valid)
        
    def test_validate_canadian_postal_code_valid(self):
        """Test valid Canadian postal codes."""
        is_valid, error = LocationService.validate_postal_code('A1A 1A1', 'CA')
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
    def test_validate_canadian_postal_code_invalid(self):
        """Test invalid Canadian postal codes."""
        # Wrong format
        is_valid, error = LocationService.validate_postal_code('123456', 'CA')
        self.assertFalse(is_valid)
        self.assertIn('Canadian', error)
        
    def test_validate_japanese_postal_code_valid(self):
        """Test valid Japanese postal codes."""
        is_valid, error = LocationService.validate_postal_code('123-4567', 'JP')
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
    def test_validate_missing_inputs(self):
        """Test validation with missing inputs."""
        is_valid, error = LocationService.validate_postal_code('', 'US')
        self.assertFalse(is_valid)
        self.assertIn('required', error)
        
        is_valid, error = LocationService.validate_postal_code('90210', '')
        self.assertFalse(is_valid)
        self.assertIn('required', error)


class LocationServiceUserLocationTests(TestCase):
    """Test user location extraction."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
    def test_get_user_location_no_address(self):
        """Test getting location when user has no address."""
        location = LocationService.get_user_location(self.user)
        
        self.assertIsInstance(location, UserLocation)
        self.assertIsNone(location.normalized_postal)
        self.assertIsNone(location.country)
        self.assertFalse(location.is_complete)
        
    def test_get_user_location_with_address(self):
        """Test getting location from user's address."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        location = LocationService.get_user_location(self.user)
        
        self.assertEqual(location.normalized_postal, '90210')
        self.assertEqual(location.country, 'US')
        self.assertEqual(location.display_postal, '90210')
        self.assertTrue(location.is_complete)
        
    def test_get_user_location_display_postal_fallback(self):
        """Test that display_postal falls back to normalized_postal."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode=None,  # No display postal
            country='US'
        )
        
        location = LocationService.get_user_location(self.user)
        
        self.assertEqual(location.display_postal, '90210')
        
    def test_get_user_location_none_user(self):
        """Test getting location for None user."""
        location = LocationService.get_user_location(None)
        
        self.assertIsInstance(location, UserLocation)
        self.assertFalse(location.is_complete)


class LocationServiceChefCoverageTests(TestCase):
    """Test chef coverage checking."""
    
    def setUp(self):
        # Create user with address
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Create postal code
        self.postal_code = PostalCode.objects.create(
            code='90210',
            display_code='90210',
            country='US',
            latitude=Decimal('34.000000'),
            longitude=Decimal('-118.000000'),
        )
        
        # Create chef
        self.chef_user = CustomUser.objects.create_user(
            username='chefuser',
            email='chef@example.com',
            password='testpass'
        )
        self.chef = Chef.objects.create(user=self.chef_user, is_verified=True)
        
    def test_has_chef_coverage_no_chef(self):
        """Test coverage check when no chef serves the area."""
        self.assertFalse(LocationService.has_chef_coverage(self.user))
        
    def test_has_chef_coverage_with_verified_chef(self):
        """Test coverage check when a verified chef serves the area."""
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal_code)
        
        self.assertTrue(LocationService.has_chef_coverage(self.user))
        
    def test_has_chef_coverage_unverified_chef(self):
        """Test that unverified chefs don't count for coverage."""
        self.chef.is_verified = False
        self.chef.save()
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal_code)
        
        self.assertFalse(LocationService.has_chef_coverage(self.user))
        
    def test_has_chef_coverage_for_area(self):
        """Test direct area coverage check."""
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal_code)
        
        self.assertTrue(LocationService.has_chef_coverage_for_area('90210', 'US'))
        self.assertFalse(LocationService.has_chef_coverage_for_area('99999', 'US'))
        
    def test_get_verified_chef_count(self):
        """Test chef count retrieval."""
        self.assertEqual(LocationService.get_verified_chef_count('90210', 'US'), 0)
        
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal_code)
        
        self.assertEqual(LocationService.get_verified_chef_count('90210', 'US'), 1)


class LocationServicePostalCodeManagementTests(TestCase):
    """Test PostalCode record management."""
    
    def test_get_or_create_postal_code_new(self):
        """Test creating a new PostalCode."""
        postal = LocationService.get_or_create_postal_code('90210', 'US')
        
        self.assertIsNotNone(postal)
        self.assertEqual(postal.code, '90210')
        self.assertEqual(str(postal.country), 'US')
        
    def test_get_or_create_postal_code_existing(self):
        """Test getting an existing PostalCode."""
        # Create first
        postal1 = LocationService.get_or_create_postal_code('90210', 'US')
        
        # Get again
        postal2 = LocationService.get_or_create_postal_code('90210', 'US')
        
        self.assertEqual(postal1.id, postal2.id)
        
    def test_get_or_create_postal_code_normalizes(self):
        """Test that get_or_create normalizes the code."""
        postal = LocationService.get_or_create_postal_code('90210-1234', 'US')
        
        self.assertEqual(postal.code, '902101234')
        
    def test_get_or_create_postal_code_invalid(self):
        """Test with invalid inputs."""
        self.assertIsNone(LocationService.get_or_create_postal_code('', 'US'))
        self.assertIsNone(LocationService.get_or_create_postal_code('90210', ''))
        self.assertIsNone(LocationService.get_or_create_postal_code(None, None))
        
    def test_get_postal_code_existing(self):
        """Test getting an existing PostalCode."""
        PostalCode.objects.create(code='90210', country='US')
        
        postal = LocationService.get_postal_code('90210', 'US')
        
        self.assertIsNotNone(postal)
        self.assertEqual(postal.code, '90210')
        
    def test_get_postal_code_not_found(self):
        """Test getting a non-existent PostalCode."""
        postal = LocationService.get_postal_code('99999', 'US')
        
        self.assertIsNone(postal)


class LocationServiceComprehensiveAccessTests(TestCase):
    """Test the comprehensive access check method."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
    def test_access_not_authenticated(self):
        """Test access check for None user."""
        result = LocationService.user_can_access_chef_features(None)
        
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'not_authenticated')
        
    def test_access_no_postal_code(self):
        """Test access check when user has no postal code.
        
        Note: The Address model validates that both postal code and country
        must be provided together, so we create an empty address.
        """
        # Create an address without postal code or country (allowed by model)
        Address.objects.create(
            user=self.user,
            normalized_postalcode=None,
            country=None
        )
        
        result = LocationService.user_can_access_chef_features(self.user)
        
        self.assertFalse(result['has_access'])
        # Will be 'no_postal_code' because that's checked first
        self.assertEqual(result['reason'], 'no_postal_code')
        
    def test_access_no_address(self):
        """Test access check when user has no address at all."""
        # User has no address relationship
        result = LocationService.user_can_access_chef_features(self.user)
        
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'no_postal_code')
        
    def test_access_no_chefs(self):
        """Test access check when no chefs serve the area."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            country='US'
        )
        
        result = LocationService.user_can_access_chef_features(self.user)
        
        self.assertFalse(result['has_access'])
        self.assertEqual(result['reason'], 'no_chefs_in_area')
        self.assertEqual(result['chef_count'], 0)
        
    def test_access_with_chefs(self):
        """Test access check when chefs are available."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            country='US'
        )
        
        postal = PostalCode.objects.create(code='90210', country='US')
        chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@example.com',
            password='pass'
        )
        chef = Chef.objects.create(user=chef_user, is_verified=True)
        ChefPostalCode.objects.create(chef=chef, postal_code=postal)
        
        result = LocationService.user_can_access_chef_features(self.user)
        
        self.assertTrue(result['has_access'])
        self.assertIsNone(result['reason'])
        self.assertEqual(result['chef_count'], 1)

