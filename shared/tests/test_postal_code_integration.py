"""
Integration tests for the postal code refactor.

These tests verify that:
1. Address model works correctly with renamed fields
2. Backwards compatibility is maintained via property aliases
3. AreaWaitlist works with the new FK structure
4. API endpoints work correctly with LocationService
5. Serializers maintain API contract
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from custom_auth.models import CustomUser, Address
from chefs.models import Chef, AreaWaitlist
from local_chefs.models import PostalCode, ChefPostalCode
from shared.services.location_service import LocationService


class AddressFieldRenameTests(TestCase):
    """Test that Address model works with renamed fields."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='addresstest',
            email='address@test.com',
            password='testpass'
        )
    
    def test_create_address_with_new_field_names(self):
        """Test creating address using new field names."""
        address = Address.objects.create(
            user=self.user,
            street='123 Main St',
            city='Los Angeles',
            state='CA',
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        self.assertEqual(address.normalized_postalcode, '90210')
        self.assertEqual(address.original_postalcode, '90210')
        
    def test_backwards_compat_property_getters(self):
        """Test that old property names still work as getters."""
        address = Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Old property names should work
        self.assertEqual(address.input_postalcode, '90210')
        self.assertEqual(address.display_postalcode, '90210')
        
    def test_backwards_compat_property_setters(self):
        """Test that old property setters normalize and store correctly."""
        # Create an empty address first (no postal or country)
        address = Address.objects.create(
            user=self.user,
            normalized_postalcode=None,
            original_postalcode=None,
            country=None
        )
        
        # Using old property name should normalize
        address.input_postalcode = '90210-1234'
        
        # Should be normalized
        self.assertEqual(address.normalized_postalcode, '902101234')
        # Original should be preserved
        self.assertEqual(address.original_postalcode, '90210-1234')
        
    def test_address_str_method(self):
        """Test Address string representation."""
        address = Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        str_repr = str(address)
        self.assertIn('90210', str_repr)
        
    def test_address_clean_normalizes(self):
        """Test that Address.clean() normalizes postal codes."""
        address = Address(
            user=self.user,
            normalized_postalcode='A1A 1A1',  # Canadian with space
            country='CA'
        )
        address.clean()
        
        # Should be normalized (no space, uppercase)
        self.assertEqual(address.normalized_postalcode, 'A1A1A1')
        # Original should be preserved
        self.assertEqual(address.original_postalcode, 'A1A 1A1')
        
    def test_address_validation_us_postal(self):
        """Test US postal code validation."""
        address = Address(
            user=self.user,
            normalized_postalcode='90210',
            country='US'
        )
        # Should not raise
        address.clean()
        
    def test_address_validation_canadian_postal(self):
        """Test Canadian postal code validation."""
        address = Address(
            user=self.user,
            normalized_postalcode='K1A0B1',  # Valid Canadian format
            country='CA'
        )
        # Should not raise
        address.clean()


class AreaWaitlistFKTests(TestCase):
    """Test AreaWaitlist with the new FK structure."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='waitlistuser',
            email='waitlist@test.com',
            password='testpass'
        )
        self.postal_code = PostalCode.objects.create(
            code='90210',
            display_code='90210',
            country='US'
        )
        
    def test_join_waitlist_creates_postal_code(self):
        """Test that join_waitlist creates PostalCode if needed."""
        # Use a postal code that doesn't exist yet
        entry, created = AreaWaitlist.join_waitlist(
            self.user,
            '90211',  # Different from setUp
            'US'
        )
        
        self.assertTrue(created)
        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.location)
        self.assertEqual(entry.location.code, '90211')
        
    def test_join_waitlist_reuses_postal_code(self):
        """Test that join_waitlist reuses existing PostalCode."""
        entry, created = AreaWaitlist.join_waitlist(
            self.user,
            '90210',  # Same as setUp
            'US'
        )
        
        self.assertTrue(created)
        self.assertEqual(entry.location.id, self.postal_code.id)
        
    def test_join_waitlist_normalizes_postal_code(self):
        """Test that join_waitlist normalizes postal codes."""
        entry, created = AreaWaitlist.join_waitlist(
            self.user,
            '90210-1234',  # With dash
            'US'
        )
        
        self.assertEqual(entry.location.code, '902101234')
        
    def test_backwards_compat_properties(self):
        """Test backwards compatibility properties on AreaWaitlist."""
        entry, _ = AreaWaitlist.join_waitlist(
            self.user,
            '90210',
            'US'
        )
        
        # Old property names should still work
        self.assertEqual(entry.postal_code, '90210')
        self.assertEqual(entry.country, 'US')
        
    def test_get_waiting_users_for_area(self):
        """Test getting waiting users for an area."""
        # Create a waitlist entry
        AreaWaitlist.join_waitlist(self.user, '90210', 'US')
        
        # Query using the class method
        waiting = AreaWaitlist.get_waiting_users_for_area('90210', 'US')
        
        self.assertEqual(waiting.count(), 1)
        self.assertEqual(waiting.first().user, self.user)
        
    def test_get_position(self):
        """Test getting waitlist position."""
        user2 = CustomUser.objects.create_user(
            username='waitlist2',
            email='waitlist2@test.com',
            password='testpass'
        )
        
        # First user joins
        AreaWaitlist.join_waitlist(self.user, '90210', 'US')
        # Second user joins
        AreaWaitlist.join_waitlist(user2, '90210', 'US')
        
        # Check positions
        pos1 = AreaWaitlist.get_position(self.user, '90210', 'US')
        pos2 = AreaWaitlist.get_position(user2, '90210', 'US')
        
        self.assertEqual(pos1, 1)
        self.assertEqual(pos2, 2)
        
    def test_get_total_waiting(self):
        """Test getting total waiting count."""
        user2 = CustomUser.objects.create_user(
            username='waitlist2',
            email='waitlist2@test.com',
            password='testpass'
        )
        
        AreaWaitlist.join_waitlist(self.user, '90210', 'US')
        AreaWaitlist.join_waitlist(user2, '90210', 'US')
        
        total = AreaWaitlist.get_total_waiting('90210', 'US')
        self.assertEqual(total, 2)


class ChefAvailabilityAPITests(APITestCase):
    """Test chef availability API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create user with address
        self.user = CustomUser.objects.create_user(
            username='apiuser',
            email='api@test.com',
            password='testpass'
        )
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Create chef postal code
        self.postal_code = PostalCode.objects.create(
            code='90210',
            display_code='90210',
            country='US',
            latitude=Decimal('34.000000'),
            longitude=Decimal('-118.000000'),
        )
        
    def test_check_availability_no_chef(self):
        """Test availability check when no chefs serve the area."""
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.get('/chefs/api/availability/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['has_chef'])
        self.assertEqual(resp.data['reason'], 'no_chefs_in_area')
        
    def test_check_availability_with_chef(self):
        """Test availability check when a chef serves the area."""
        # Create verified chef
        chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass'
        )
        chef = Chef.objects.create(user=chef_user, is_verified=True)
        ChefPostalCode.objects.create(chef=chef, postal_code=self.postal_code)
        
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.get('/chefs/api/availability/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['has_chef'])
        
    def test_check_availability_unverified_chef_not_counted(self):
        """Test that unverified chefs don't count for availability."""
        # Create unverified chef
        chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass'
        )
        chef = Chef.objects.create(user=chef_user, is_verified=False)
        ChefPostalCode.objects.create(chef=chef, postal_code=self.postal_code)
        
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.get('/chefs/api/availability/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['has_chef'])
        
    def test_join_waitlist(self):
        """Test joining the area waitlist."""
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.post('/chefs/api/area-waitlist/join/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertTrue(resp.data['on_waitlist'])
        self.assertEqual(resp.data['position'], 1)
        
    def test_join_waitlist_when_chef_available(self):
        """Test that joining waitlist fails when chefs are available."""
        # Create verified chef
        chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass'
        )
        chef = Chef.objects.create(user=chef_user, is_verified=True)
        ChefPostalCode.objects.create(chef=chef, postal_code=self.postal_code)
        
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.post('/chefs/api/area-waitlist/join/')
        
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['success'])
        self.assertTrue(resp.data['has_chef'])
        
    def test_leave_waitlist(self):
        """Test leaving the area waitlist."""
        # First join
        AreaWaitlist.join_waitlist(self.user, '90210', 'US')
        
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.delete('/chefs/api/area-waitlist/leave/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])
        self.assertFalse(resp.data['on_waitlist'])
        
    def test_waitlist_status(self):
        """Test getting waitlist status."""
        # Join waitlist
        AreaWaitlist.join_waitlist(self.user, '90210', 'US')
        
        self.client.force_authenticate(user=self.user)
        
        resp = self.client.get('/chefs/api/area-waitlist/status/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['on_waitlist'])
        self.assertEqual(resp.data['position'], 1)


class AddressSerializerAPITests(APITestCase):
    """Test that address serializers maintain API contract."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='serializeruser',
            email='serializer@test.com',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        
    def test_address_api_returns_input_postalcode(self):
        """Test that API still returns input_postalcode for backwards compat."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        resp = self.client.get('/auth/api/address_details/')
        
        self.assertEqual(resp.status_code, 200)
        # Should return input_postalcode for backwards compatibility
        self.assertIn('input_postalcode', resp.data)
        self.assertEqual(resp.data['input_postalcode'], '90210')
        
    def test_address_api_update_via_input_postalcode(self):
        """Test that API accepts input_postalcode for updates."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Update address via update_profile endpoint
        resp = self.client.post('/auth/api/update_profile/', {
            'address': {
                'input_postalcode': '90211',
                'country': 'US'
            }
        }, format='json')
        
        self.assertEqual(resp.status_code, 200)
        
        # Verify the update
        self.user.refresh_from_db()
        self.assertEqual(self.user.address.normalized_postalcode, '90211')


class LocationServiceIntegrationTests(TestCase):
    """Test LocationService integration with models."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='locationuser',
            email='location@test.com',
            password='testpass'
        )
        
    def test_location_service_with_new_address_fields(self):
        """Test LocationService works with new Address field names."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        location = LocationService.get_user_location(self.user)
        
        self.assertEqual(location.normalized_postal, '90210')
        self.assertEqual(location.country, 'US')
        self.assertTrue(location.is_complete)
        
    def test_has_chef_coverage_integration(self):
        """Test chef coverage check end-to-end."""
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Initially no chef coverage
        self.assertFalse(LocationService.has_chef_coverage(self.user))
        
        # Add a verified chef
        postal = PostalCode.objects.create(code='90210', country='US')
        chef_user = CustomUser.objects.create_user(
            username='chef',
            email='chef@test.com',
            password='testpass'
        )
        chef = Chef.objects.create(user=chef_user, is_verified=True)
        ChefPostalCode.objects.create(chef=chef, postal_code=postal)
        
        # Now should have coverage
        self.assertTrue(LocationService.has_chef_coverage(self.user))
        
    def test_get_or_create_postal_code_integration(self):
        """Test PostalCode creation via LocationService."""
        # Create via LocationService
        postal = LocationService.get_or_create_postal_code('90210-1234', 'US')
        
        self.assertIsNotNone(postal)
        self.assertEqual(postal.code, '902101234')  # Normalized
        
        # Verify it's in the database
        self.assertTrue(PostalCode.objects.filter(code='902101234', country='US').exists())


class ChefServesMyAreaTests(APITestCase):
    """Test chef_serves_my_area endpoint with refactored code."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create user with address
        self.user = CustomUser.objects.create_user(
            username='areauser',
            email='area@test.com',
            password='testpass'
        )
        Address.objects.create(
            user=self.user,
            normalized_postalcode='90210',
            original_postalcode='90210',
            country='US'
        )
        
        # Create chef
        chef_user = CustomUser.objects.create_user(
            username='areachef',
            email='areachef@test.com',
            password='testpass'
        )
        self.chef = Chef.objects.create(user=chef_user)
        
        # Create postal code
        self.postal = PostalCode.objects.create(
            code='90210',
            country='US'
        )
        
    def test_chef_serves_area_true(self):
        """Test endpoint returns true when chef serves user's area."""
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal)
        
        self.client.force_authenticate(user=self.user)
        
        # Correct URL path
        resp = self.client.get(f'/chefs/api/public/{self.chef.id}/serves-my-area/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['serves'])
        self.assertEqual(resp.data['user_postal_code'], '90210')
        
    def test_chef_serves_area_false(self):
        """Test endpoint returns false when chef doesn't serve user's area."""
        # Chef serves different postal code
        other_postal = PostalCode.objects.create(code='90211', country='US')
        ChefPostalCode.objects.create(chef=self.chef, postal_code=other_postal)
        
        self.client.force_authenticate(user=self.user)
        
        # Correct URL path
        resp = self.client.get(f'/chefs/api/public/{self.chef.id}/serves-my-area/')
        
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['serves'])

