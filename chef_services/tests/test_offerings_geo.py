from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier
from local_chefs.models import PostalCode, ChefPostalCode


class OfferingsDistanceFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Viewer postal code (Los Angeles area)
        self.viewer_postal = PostalCode.objects.create(
            code='90001',
            display_code='90001',
            country='US',
            latitude=Decimal('34.000000'),
            longitude=Decimal('-118.000000'),
        )

        # Nearby chef postal code (~3 miles away)
        self.near_postal = PostalCode.objects.create(
            code='90002',
            display_code='90002',
            country='US',
            latitude=Decimal('34.030000'),
            longitude=Decimal('-118.000000'),
        )

        # Distant chef postal code (~70 miles away)
        self.far_postal = PostalCode.objects.create(
            code='90123',
            display_code='90123',
            country='US',
            latitude=Decimal('34.900000'),
            longitude=Decimal('-119.000000'),
        )

        self.chef_near = self._create_chef('near_chef', self.near_postal)
        self.chef_far = self._create_chef('far_chef', self.far_postal)
        self.chef_unlimited = self._create_chef('unlimited_chef', self.far_postal)

        self.off_near = ChefServiceOffering.objects.create(
            chef=self.chef_near,
            service_type='home_chef',
            title='Near Offering',
            active=True,
            max_travel_miles=25,
        )
        self.off_far = ChefServiceOffering.objects.create(
            chef=self.chef_far,
            service_type='home_chef',
            title='Far Offering',
            active=True,
            max_travel_miles=25,
        )
        self.off_unlimited = ChefServiceOffering.objects.create(
            chef=self.chef_unlimited,
            service_type='home_chef',
            title='Unlimited Offering',
            active=True,
            max_travel_miles=None,
        )

        for offering in (self.off_near, self.off_far, self.off_unlimited):
            ChefServicePriceTier.objects.create(
                offering=offering,
                household_min=1,
                household_max=4,
                currency='usd',
                desired_unit_amount_cents=10000,
                active=True,
            )

    def _create_chef(self, username, postal):
        user = CustomUser.objects.create_user(username=username, email=f"{username}@example.com", password='pass')
        chef = Chef.objects.create(user=user)
        ChefPostalCode.objects.create(chef=chef, postal_code=postal)
        return chef

    def test_filter_by_viewer_postal_code(self):
        resp = self.client.get('/services/offerings/', {'postal_code': '90001', 'country': 'US'})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        ids = {item['id'] for item in data}
        self.assertIn(self.off_near.id, ids)
        self.assertIn(self.off_unlimited.id, ids)
        self.assertNotIn(self.off_far.id, ids)

    def test_auth_user_fallback_to_address(self):
        viewer = CustomUser.objects.create_user(username='viewer', email='viewer@example.com', password='pass')
        Address.objects.create(
            user=viewer,
            normalized_postalcode='90001',
            original_postalcode='90001',
            country='US',
            latitude=Decimal('34.000000'),
            longitude=Decimal('-118.000000'),
        )
        self.client.force_authenticate(user=viewer)
        resp = self.client.get('/services/offerings/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        ids = {item['id'] for item in data}
        self.assertIn(self.off_near.id, ids)
        self.assertIn(self.off_unlimited.id, ids)
        self.assertNotIn(self.off_far.id, ids)

    def test_no_filter_when_location_unknown(self):
        resp = self.client.get('/services/offerings/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        ids = {item['id'] for item in data}
        self.assertEqual(ids, {self.off_near.id, self.off_far.id, self.off_unlimited.id})
