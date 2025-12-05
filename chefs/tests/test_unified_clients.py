"""
Tests for Unified Clients API - combines platform users and manual contacts.

Tests cover:
- Unified client list endpoint
- Filtering by source (platform/contact)
- Filtering by dietary preferences
- Filtering by allergies
- Search functionality
- Sorting options
- Dietary summary endpoint
- Security (chef isolation)
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefCustomerConnection
from crm.models import Lead, LeadHouseholdMember
from meals.models import DietaryPreference


@pytest.mark.django_db
class UnifiedClientListTests(TestCase):
    """Test unified client list endpoint."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create chef
        self.chef_user = CustomUser.objects.create_user(
            username='unifiedchef',
            email='unifiedchef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        # Create dietary preferences
        self.vegan_pref, _ = DietaryPreference.objects.get_or_create(name='Vegan')
        self.keto_pref, _ = DietaryPreference.objects.get_or_create(name='Keto')
        
        # Create a platform user customer
        self.platform_customer = CustomUser.objects.create_user(
            username='platformcustomer',
            email='platform@test.com',
            password='testpass123',
            first_name='Platform',
            last_name='User'
        )
        self.platform_customer.dietary_preferences.add(self.vegan_pref)
        self.platform_customer.allergies = ['Peanuts']
        self.platform_customer.save()
        
        # Create connection
        self.connection = ChefCustomerConnection.objects.create(
            chef=self.chef,
            customer=self.platform_customer,
            status='accepted'
        )
        
        # Create a manual contact
        self.manual_contact = Lead.objects.create(
            owner=self.chef_user,
            first_name='Manual',
            last_name='Contact',
            dietary_preferences=['Keto'],
            allergies=['Shellfish'],
            status='won'
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_unified_list_returns_both_sources(self):
        """Should return both platform users and manual contacts."""
        response = self.client.get('/chefs/api/me/all-clients/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        # Should have 2 clients
        self.assertEqual(len(results), 2)
        
        # Check source types
        source_types = [r['source_type'] for r in results]
        self.assertIn('platform', source_types)
        self.assertIn('contact', source_types)
    
    def test_summary_includes_counts(self):
        """Summary should include platform and contact counts."""
        response = self.client.get('/chefs/api/me/all-clients/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summary = response.data.get('summary', {})
        
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['platform'], 1)
        self.assertEqual(summary['contacts'], 1)
    
    def test_filter_by_source_platform(self):
        """Should filter to only platform users."""
        response = self.client.get('/chefs/api/me/all-clients/?source=platform')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_type'], 'platform')
    
    def test_filter_by_source_contact(self):
        """Should filter to only manual contacts."""
        response = self.client.get('/chefs/api/me/all-clients/?source=contact')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_type'], 'contact')
    
    def test_filter_by_dietary_preference(self):
        """Should filter by dietary preference."""
        response = self.client.get('/chefs/api/me/all-clients/?dietary=Vegan')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertIn('Vegan', results[0]['dietary_preferences'])
    
    def test_filter_by_allergy(self):
        """Should filter by allergy."""
        response = self.client.get('/chefs/api/me/all-clients/?allergy=Peanuts')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertIn('Peanuts', results[0]['allergies'])
    
    def test_search_by_name(self):
        """Should search by name."""
        response = self.client.get('/chefs/api/me/all-clients/?search=Platform')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_type'], 'platform')
    
    def test_search_by_email(self):
        """Should search by email."""
        response = self.client.get('/chefs/api/me/all-clients/?search=platform@test')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
    
    def test_ordering_by_name(self):
        """Should order by name."""
        response = self.client.get('/chefs/api/me/all-clients/?ordering=name')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        names = [r['name'] for r in results]
        self.assertEqual(names, sorted(names))
    
    def test_dietary_breakdown_in_summary(self):
        """Summary should include dietary breakdown."""
        response = self.client.get('/chefs/api/me/all-clients/')
        
        summary = response.data.get('summary', {})
        dietary = summary.get('dietary_breakdown', {})
        
        self.assertIn('Vegan', dietary)
        self.assertIn('Keto', dietary)


@pytest.mark.django_db
class UnifiedClientDetailTests(TestCase):
    """Test unified client detail endpoint."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.chef_user = CustomUser.objects.create_user(
            username='detailchef',
            email='detailchef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        # Platform customer
        self.platform_customer = CustomUser.objects.create_user(
            username='detailcustomer',
            email='detail@test.com',
            password='testpass123',
            first_name='Detail',
            last_name='Customer'
        )
        self.connection = ChefCustomerConnection.objects.create(
            chef=self.chef,
            customer=self.platform_customer,
            status='accepted'
        )
        
        # Manual contact with household
        self.manual_contact = Lead.objects.create(
            owner=self.chef_user,
            first_name='Family',
            last_name='Lead',
            dietary_preferences=['Vegan'],
            status='won'
        )
        LeadHouseholdMember.objects.create(
            lead=self.manual_contact,
            name='Child',
            relationship='child',
            dietary_preferences=['Vegetarian']
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_get_platform_client_detail(self):
        """Should get platform client by prefixed ID."""
        response = self.client.get(f'/chefs/api/me/all-clients/platform_{self.platform_customer.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source_type'], 'platform')
        self.assertEqual(response.data['name'], 'Detail Customer')
    
    def test_get_contact_client_detail(self):
        """Should get contact client by prefixed ID."""
        response = self.client.get(f'/chefs/api/me/all-clients/contact_{self.manual_contact.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source_type'], 'contact')
        self.assertEqual(response.data['name'], 'Family Lead')
    
    def test_contact_detail_includes_household(self):
        """Contact detail should include household members."""
        response = self.client.get(f'/chefs/api/me/all-clients/contact_{self.manual_contact.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        household = response.data.get('household_members', [])
        
        self.assertEqual(len(household), 1)
        self.assertEqual(household[0]['name'], 'Child')
    
    def test_invalid_id_format_returns_400(self):
        """Should return 400 for invalid ID format."""
        response = self.client.get('/chefs/api/me/all-clients/invalid_123/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_nonexistent_client_returns_404(self):
        """Should return 404 for nonexistent client."""
        response = self.client.get('/chefs/api/me/all-clients/platform_99999/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
class UnifiedClientSecurityTests(TestCase):
    """Security tests for unified clients API."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Chef 1
        self.chef1_user = CustomUser.objects.create_user(
            username='secchef1',
            email='secchef1@test.com',
            password='testpass123'
        )
        self.chef1 = Chef.objects.create(user=self.chef1_user)
        
        # Chef 2
        self.chef2_user = CustomUser.objects.create_user(
            username='secchef2',
            email='secchef2@test.com',
            password='testpass123'
        )
        self.chef2 = Chef.objects.create(user=self.chef2_user)
        
        # Chef 1's customer
        self.chef1_customer = CustomUser.objects.create_user(
            username='chef1customer',
            email='chef1cust@test.com',
            password='testpass123'
        )
        ChefCustomerConnection.objects.create(
            chef=self.chef1,
            customer=self.chef1_customer,
            status='accepted'
        )
        
        # Chef 1's contact
        self.chef1_contact = Lead.objects.create(
            owner=self.chef1_user,
            first_name='Chef1',
            last_name='Contact',
            status='won'
        )
    
    def test_chef_cannot_see_other_chef_clients(self):
        """Chef should only see their own clients."""
        self.client.force_authenticate(user=self.chef2_user)
        
        response = self.client.get('/chefs/api/me/all-clients/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        self.assertEqual(len(results), 0)
    
    def test_chef_cannot_access_other_chef_client_detail(self):
        """Chef should not access another chef's client details."""
        self.client.force_authenticate(user=self.chef2_user)
        
        response = self.client.get(f'/chefs/api/me/all-clients/contact_{self.chef1_contact.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_access_denied(self):
        """Unauthenticated users should be denied."""
        response = self.client.get('/chefs/api/me/all-clients/')
        
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


@pytest.mark.django_db
class DietarySummaryTests(TestCase):
    """Test dietary summary endpoint."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.chef_user = CustomUser.objects.create_user(
            username='summarychef',
            email='summarychef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        # Create dietary preference
        self.vegan_pref, _ = DietaryPreference.objects.get_or_create(name='Vegan')
        
        # Platform customer with preferences
        self.customer = CustomUser.objects.create_user(
            username='summcust',
            email='summcust@test.com',
            password='testpass123'
        )
        self.customer.dietary_preferences.add(self.vegan_pref)
        self.customer.allergies = ['Peanuts', 'Tree nuts']
        self.customer.save()
        
        ChefCustomerConnection.objects.create(
            chef=self.chef,
            customer=self.customer,
            status='accepted'
        )
        
        # Manual contact
        self.contact = Lead.objects.create(
            owner=self.chef_user,
            first_name='Contact',
            dietary_preferences=['Keto'],
            allergies=['Shellfish'],
            status='won'
        )
        LeadHouseholdMember.objects.create(
            lead=self.contact,
            name='Child',
            dietary_preferences=['Vegetarian'],
            allergies=['Milk']
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_dietary_summary_returns_counts(self):
        """Should return dietary preference counts."""
        response = self.client.get('/chefs/api/me/dietary-summary/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['total_clients'], 2)
        self.assertGreaterEqual(data['total_people'], 3)  # 2 primary + 1 household member
    
    def test_dietary_summary_includes_preferences(self):
        """Should include dietary preference breakdown."""
        response = self.client.get('/chefs/api/me/dietary-summary/')
        
        dietary = response.data.get('dietary_preferences', {})
        
        self.assertIn('Vegan', dietary)
        self.assertIn('Keto', dietary)
        self.assertIn('Vegetarian', dietary)
    
    def test_dietary_summary_includes_allergies(self):
        """Should include allergy breakdown."""
        response = self.client.get('/chefs/api/me/dietary-summary/')
        
        allergies = response.data.get('allergies', {})
        
        self.assertIn('Peanuts', allergies)
        self.assertIn('Shellfish', allergies)
        self.assertIn('Milk', allergies)


@pytest.mark.django_db
class UnifiedClientFilterCombinationTests(TestCase):
    """Test combined filter scenarios."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.chef_user = CustomUser.objects.create_user(
            username='filterchef',
            email='filterchef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        # Create contacts with different attributes
        Lead.objects.create(
            owner=self.chef_user,
            first_name='Vegan',
            last_name='Client',
            dietary_preferences=['Vegan'],
            allergies=['Peanuts'],
            status='won'
        )
        Lead.objects.create(
            owner=self.chef_user,
            first_name='Keto',
            last_name='Client',
            dietary_preferences=['Keto'],
            allergies=['Shellfish'],
            status='won'
        )
        Lead.objects.create(
            owner=self.chef_user,
            first_name='Vegan',
            last_name='Allergic',
            dietary_preferences=['Vegan'],
            allergies=['Shellfish'],
            status='won'
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_filter_dietary_and_allergy(self):
        """Should filter by both dietary and allergy."""
        response = self.client.get('/chefs/api/me/all-clients/?dietary=Vegan&allergy=Shellfish')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Vegan Allergic')
    
    def test_filter_source_and_dietary(self):
        """Should filter by source and dietary."""
        response = self.client.get('/chefs/api/me/all-clients/?source=contact&dietary=Vegan')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        # Should find 2 vegan contacts
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn('Vegan', r['dietary_preferences'])
    
    def test_search_and_filter(self):
        """Should combine search with filter."""
        response = self.client.get('/chefs/api/me/all-clients/?search=Keto&dietary=Keto')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', [])
        
        self.assertEqual(len(results), 1)
