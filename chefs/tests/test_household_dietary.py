"""
Tests for Lead Household and Dietary Tracking functionality.

Tests cover:
- LeadHouseholdMember model
- Lead dietary fields (preferences, allergies)
- API endpoints for household member management
- Serializers for household data
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from custom_auth.models import CustomUser
from chefs.models import Chef
from crm.models import Lead, LeadInteraction, LeadHouseholdMember


# =============================================================================
# Model Tests
# =============================================================================

class LeadDietaryFieldsTests(TestCase):
    """Test Lead model dietary tracking fields."""
    
    def setUp(self):
        self.chef_user = CustomUser.objects.create_user(
            username='testchef_dietary',
            email='chef_dietary@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
    
    def test_lead_with_dietary_preferences(self):
        """Lead should store dietary preferences as array."""
        lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='John',
            last_name='Doe',
            dietary_preferences=['Vegan', 'Gluten-Free'],
            status='won'
        )
        lead.refresh_from_db()
        self.assertEqual(lead.dietary_preferences, ['Vegan', 'Gluten-Free'])
    
    def test_lead_with_allergies(self):
        """Lead should store allergies as array."""
        lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Jane',
            last_name='Doe',
            allergies=['Peanuts', 'Shellfish'],
            status='won'
        )
        lead.refresh_from_db()
        self.assertEqual(lead.allergies, ['Peanuts', 'Shellfish'])
    
    def test_lead_with_custom_allergies(self):
        """Lead should store custom allergies."""
        lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Bob',
            allergies=['Peanuts'],
            custom_allergies=['Mango', 'Papaya'],
            status='won'
        )
        lead.refresh_from_db()
        self.assertIn('Mango', lead.custom_allergies)
        self.assertIn('Papaya', lead.custom_allergies)
    
    def test_lead_household_size_default(self):
        """Lead household_size should default to 1."""
        lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Solo',
            status='won'
        )
        self.assertEqual(lead.household_size, 1)
    
    def test_lead_empty_dietary_fields(self):
        """Lead dietary fields should default to empty lists."""
        lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Minimal',
            status='won'
        )
        lead.refresh_from_db()
        self.assertEqual(lead.dietary_preferences, [])
        self.assertEqual(lead.allergies, [])
        self.assertEqual(lead.custom_allergies, [])


class LeadHouseholdMemberModelTests(TestCase):
    """Test LeadHouseholdMember model."""
    
    def setUp(self):
        self.chef_user = CustomUser.objects.create_user(
            username='testchef_hh',
            email='chef_hh@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        self.lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='John',
            last_name='Smith',
            status='won'
        )
    
    def test_create_household_member(self):
        """Should create a household member linked to lead."""
        member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Jane Smith',
            relationship='spouse',
            age=35
        )
        self.assertEqual(member.lead, self.lead)
        self.assertEqual(member.name, 'Jane Smith')
        self.assertEqual(member.relationship, 'spouse')
        self.assertEqual(member.age, 35)
    
    def test_household_member_dietary_preferences(self):
        """Household member should store dietary preferences."""
        member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Child',
            dietary_preferences=['Vegetarian', 'Nut-Free']
        )
        member.refresh_from_db()
        self.assertEqual(member.dietary_preferences, ['Vegetarian', 'Nut-Free'])
    
    def test_household_member_allergies(self):
        """Household member should store allergies."""
        member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Child',
            allergies=['Milk', 'Egg']
        )
        member.refresh_from_db()
        self.assertEqual(member.allergies, ['Milk', 'Egg'])
    
    def test_household_member_cascade_delete(self):
        """Deleting lead should delete household members."""
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member1')
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member2')
        self.assertEqual(LeadHouseholdMember.objects.filter(lead=self.lead).count(), 2)
        
        lead_id = self.lead.id
        self.lead.delete()
        self.assertEqual(LeadHouseholdMember.objects.filter(lead_id=lead_id).count(), 0)
    
    def test_household_member_str(self):
        """String representation should include name and lead."""
        member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Test Member'
        )
        self.assertIn('Test Member', str(member))
    
    def test_lead_household_members_relation(self):
        """Lead should access household_members through relation."""
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member1')
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member2')
        
        self.assertEqual(self.lead.household_members.count(), 2)
        names = list(self.lead.household_members.values_list('name', flat=True))
        self.assertIn('Member1', names)
        self.assertIn('Member2', names)


# =============================================================================
# API Tests
# =============================================================================

@pytest.mark.django_db
class LeadHouseholdAPITests(TestCase):
    """Test API endpoints for household member management."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create chef user
        self.chef_user = CustomUser.objects.create_user(
            username='apichef_hh',
            email='apichef_hh@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        # Create a lead for testing
        self.lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Test',
            last_name='Client',
            status='won'
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.chef_user)
    
    def test_create_lead_with_dietary_info(self):
        """POST /api/chefs/me/leads/ should accept dietary info."""
        response = self.client.post('/chefs/api/me/leads/', {
            'first_name': 'New',
            'last_name': 'Client',
            'dietary_preferences': ['Vegan', 'Gluten-Free'],
            'allergies': ['Peanuts'],
            'household_size': 3,
            'status': 'won'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['dietary_preferences'], ['Vegan', 'Gluten-Free'])
        self.assertEqual(response.data['allergies'], ['Peanuts'])
        self.assertEqual(response.data['household_size'], 3)
    
    def test_create_lead_with_household_members(self):
        """POST /api/chefs/me/leads/ should create household members."""
        response = self.client.post('/chefs/api/me/leads/', {
            'first_name': 'Parent',
            'last_name': 'Smith',
            'status': 'won',
            'household_members': [
                {
                    'name': 'Child Smith',
                    'relationship': 'child',
                    'age': 10,
                    'dietary_preferences': ['Nut-Free'],
                    'allergies': ['Peanuts', 'Tree nuts']
                }
            ]
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify household member was created
        lead_id = response.data['id']
        lead = Lead.objects.get(id=lead_id)
        self.assertEqual(lead.household_members.count(), 1)
        
        member = lead.household_members.first()
        self.assertEqual(member.name, 'Child Smith')
        self.assertEqual(member.dietary_preferences, ['Nut-Free'])
    
    def test_get_lead_includes_household_members(self):
        """GET /api/chefs/me/leads/{id}/ should include household_members."""
        LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Spouse',
            relationship='spouse',
            dietary_preferences=['Vegetarian']
        )
        
        response = self.client.get(f'/chefs/api/me/leads/{self.lead.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('household_members', response.data)
        self.assertEqual(len(response.data['household_members']), 1)
        self.assertEqual(response.data['household_members'][0]['name'], 'Spouse')
    
    def test_get_household_members_list(self):
        """GET /api/chefs/me/leads/{id}/household/ should list members."""
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member1')
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member2')
        
        response = self.client.get(f'/chefs/api/me/leads/{self.lead.id}/household/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_add_household_member(self):
        """POST /api/chefs/me/leads/{id}/household/ should add member."""
        response = self.client.post(f'/chefs/api/me/leads/{self.lead.id}/household/', {
            'name': 'New Member',
            'relationship': 'child',
            'age': 8,
            'dietary_preferences': ['Dairy-Free'],
            'allergies': ['Milk']
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Member')
        self.assertEqual(response.data['relationship'], 'child')
        self.assertEqual(response.data['age'], 8)
    
    def test_add_household_member_updates_household_size(self):
        """Adding household member should update lead.household_size."""
        self.lead.household_size = 1
        self.lead.save()
        
        self.client.post(f'/chefs/api/me/leads/{self.lead.id}/household/', {
            'name': 'New Member'
        }, format='json')
        
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.household_size, 2)  # 1 member + primary = 2
    
    def test_update_household_member(self):
        """PATCH /api/chefs/me/leads/{id}/household/{mid}/ should update member."""
        member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Original Name',
            age=30
        )
        
        response = self.client.patch(
            f'/chefs/api/me/leads/{self.lead.id}/household/{member.id}/',
            {'name': 'Updated Name', 'age': 31},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertEqual(member.name, 'Updated Name')
        self.assertEqual(member.age, 31)
    
    def test_delete_household_member(self):
        """DELETE /api/chefs/me/leads/{id}/household/{mid}/ should remove member."""
        member = LeadHouseholdMember.objects.create(lead=self.lead, name='To Delete')
        
        response = self.client.delete(
            f'/chefs/api/me/leads/{self.lead.id}/household/{member.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LeadHouseholdMember.objects.filter(id=member.id).exists())
    
    def test_household_member_404_for_wrong_lead(self):
        """Should return 404 if member doesn't belong to lead."""
        # Create another lead
        other_lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Other',
            status='won'
        )
        member = LeadHouseholdMember.objects.create(lead=other_lead, name='Other Member')
        
        # Try to access member through wrong lead
        response = self.client.get(
            f'/chefs/api/me/leads/{self.lead.id}/household/{member.id}/'
        )
        
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED])
    
    def test_lead_list_includes_household_count(self):
        """GET /api/chefs/me/leads/ should include household_member_count."""
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member1')
        LeadHouseholdMember.objects.create(lead=self.lead, name='Member2')
        
        response = self.client.get('/chefs/api/me/leads/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        
        # Find our lead in results
        lead_data = next((l for l in results if l['id'] == self.lead.id), None)
        self.assertIsNotNone(lead_data)
        self.assertEqual(lead_data['household_member_count'], 2)


@pytest.mark.django_db
class LeadDietaryAPISecurityTests(TestCase):
    """Security tests for dietary/household API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create two chefs
        self.chef1_user = CustomUser.objects.create_user(
            username='chef1_sec',
            email='chef1_sec@test.com',
            password='pass123'
        )
        self.chef1 = Chef.objects.create(user=self.chef1_user)
        
        self.chef2_user = CustomUser.objects.create_user(
            username='chef2_sec',
            email='chef2_sec@test.com',
            password='pass123'
        )
        self.chef2 = Chef.objects.create(user=self.chef2_user)
        
        # Create lead owned by chef1
        self.lead = Lead.objects.create(
            owner=self.chef1_user,
            first_name='Chef1 Client',
            status='won'
        )
        self.member = LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Family Member'
        )
    
    def test_cannot_access_other_chef_lead(self):
        """Chef should not access another chef's lead."""
        self.client.force_authenticate(user=self.chef2_user)
        
        response = self.client.get(f'/chefs/api/me/leads/{self.lead.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_cannot_add_member_to_other_chef_lead(self):
        """Chef should not add household member to another chef's lead."""
        self.client.force_authenticate(user=self.chef2_user)
        
        response = self.client.post(
            f'/chefs/api/me/leads/{self.lead.id}/household/',
            {'name': 'Intruder'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_cannot_delete_other_chef_member(self):
        """Chef should not delete another chef's household member."""
        self.client.force_authenticate(user=self.chef2_user)
        
        response = self.client.delete(
            f'/chefs/api/me/leads/{self.lead.id}/household/{self.member.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_cannot_access(self):
        """Unauthenticated users should not access household endpoints."""
        response = self.client.get(f'/chefs/api/me/leads/{self.lead.id}/household/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


@pytest.mark.django_db
class LeadUpdateDietaryTests(TestCase):
    """Test updating dietary info on leads."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.chef_user = CustomUser.objects.create_user(
            username='updatechef',
            email='updatechef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        self.lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Update',
            last_name='Test',
            dietary_preferences=['Vegan'],
            allergies=['Peanuts'],
            status='won'
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_update_lead_dietary_preferences(self):
        """PATCH should update dietary preferences."""
        response = self.client.patch(f'/chefs/api/me/leads/{self.lead.id}/', {
            'dietary_preferences': ['Vegetarian', 'Gluten-Free']
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.dietary_preferences, ['Vegetarian', 'Gluten-Free'])
    
    def test_update_lead_allergies(self):
        """PATCH should update allergies."""
        response = self.client.patch(f'/chefs/api/me/leads/{self.lead.id}/', {
            'allergies': ['Shellfish', 'Soy']
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.allergies, ['Shellfish', 'Soy'])
    
    def test_update_lead_household_size(self):
        """PATCH should update household_size."""
        response = self.client.patch(f'/chefs/api/me/leads/{self.lead.id}/', {
            'household_size': 5
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.household_size, 5)


# =============================================================================
# Serializer Tests
# =============================================================================

class LeadSerializerTests(TestCase):
    """Test lead serializers include dietary/household data."""
    
    def setUp(self):
        self.chef_user = CustomUser.objects.create_user(
            username='serializerchef',
            email='serializerchef@test.com',
            password='testpass123'
        )
        self.lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Serializer',
            last_name='Test',
            dietary_preferences=['Keto', 'Low-Sodium'],
            allergies=['Gluten'],
            household_size=4,
            status='won'
        )
        LeadHouseholdMember.objects.create(
            lead=self.lead,
            name='Member 1',
            dietary_preferences=['Vegetarian']
        )
    
    def test_lead_list_serializer_includes_dietary_fields(self):
        """LeadListSerializer should include dietary fields."""
        from chefs.api.serializers import LeadListSerializer
        
        serializer = LeadListSerializer(self.lead)
        data = serializer.data
        
        self.assertIn('dietary_preferences', data)
        self.assertIn('allergies', data)
        self.assertIn('household_size', data)
        self.assertIn('household_member_count', data)
        self.assertEqual(data['household_member_count'], 1)
    
    def test_lead_detail_serializer_includes_household_members(self):
        """LeadDetailSerializer should include household_members."""
        from chefs.api.serializers import LeadDetailSerializer
        
        serializer = LeadDetailSerializer(self.lead)
        data = serializer.data
        
        self.assertIn('household_members', data)
        self.assertEqual(len(data['household_members']), 1)
        self.assertEqual(data['household_members'][0]['name'], 'Member 1')
        self.assertEqual(data['household_members'][0]['dietary_preferences'], ['Vegetarian'])
    
    def test_lead_update_serializer_fields(self):
        """LeadUpdateSerializer should allow updating dietary fields."""
        from chefs.api.serializers import LeadUpdateSerializer
        
        serializer = LeadUpdateSerializer(
            self.lead,
            data={'dietary_preferences': ['Paleo']},
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.dietary_preferences, ['Paleo'])


# =============================================================================
# Edge Case Tests
# =============================================================================

class LeadHouseholdEdgeCaseTests(TestCase):
    """Edge case tests for household functionality."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.chef_user = CustomUser.objects.create_user(
            username='edgechef',
            email='edgechef@test.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        
        self.lead = Lead.objects.create(
            owner=self.chef_user,
            first_name='Edge',
            last_name='Case',
            status='won'
        )
        
        self.client.force_authenticate(user=self.chef_user)
    
    def test_create_member_without_name_fails(self):
        """POST should fail if name is missing."""
        response = self.client.post(
            f'/chefs/api/me/leads/{self.lead.id}/household/',
            {'relationship': 'spouse'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_empty_dietary_preferences_array(self):
        """Should accept empty arrays for dietary fields."""
        response = self.client.post('/chefs/api/me/leads/', {
            'first_name': 'Empty',
            'dietary_preferences': [],
            'allergies': [],
            'status': 'won'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['dietary_preferences'], [])
    
    def test_large_household(self):
        """Should handle household with many members."""
        for i in range(10):
            LeadHouseholdMember.objects.create(
                lead=self.lead,
                name=f'Member {i}',
                age=20 + i
            )
        
        response = self.client.get(f'/chefs/api/me/leads/{self.lead.id}/household/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)
    
    def test_member_with_all_fields(self):
        """Should handle member with all fields populated."""
        response = self.client.post(
            f'/chefs/api/me/leads/{self.lead.id}/household/',
            {
                'name': 'Complete Member',
                'relationship': 'spouse',
                'age': 40,
                'dietary_preferences': ['Vegan', 'Gluten-Free', 'Low-Sodium'],
                'allergies': ['Peanuts', 'Tree nuts', 'Shellfish'],
                'custom_allergies': ['Mango', 'Papaya'],
                'notes': 'Very detailed notes about dietary requirements'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['dietary_preferences']), 3)
        self.assertEqual(len(response.data['allergies']), 3)
    
    def test_household_404_for_nonexistent_lead(self):
        """Should return 404 for nonexistent lead."""
        response = self.client.get('/chefs/api/me/leads/99999/household/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_household_404_for_nonexistent_member(self):
        """Should return 404 for nonexistent member."""
        response = self.client.delete(
            f'/chefs/api/me/leads/{self.lead.id}/household/99999/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
