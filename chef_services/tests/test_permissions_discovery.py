from django.urls import reverse
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ChefServicesPermissionsDiscoveryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username="u1", email="u1@example.com", password="pass")
        self.chef_user = CustomUser.objects.create_user(username="chef", email="chef@example.com", password="pass")
        self.chef = Chef.objects.create(user=self.chef_user)

    def test_offerings_post_requires_auth_and_chef(self):
        url = reverse('service_offerings')
        # Anonymous
        resp = self.client.post(url, {"service_type": "home_chef", "title": "X"}, format='json', secure=True)
        self.assertEqual(resp.status_code, 401)

        # Auth but not a chef -> 403
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(url, {"service_type": "home_chef", "title": "X"}, format='json', secure=True)
        self.assertEqual(resp.status_code, 403)

        # Chef -> 201
        self.client.force_authenticate(user=self.chef_user)
        resp = self.client.post(url, {"service_type": "home_chef", "title": "X"}, format='json', secure=True)
        self.assertEqual(resp.status_code, 201)

    def test_public_discovery_hides_stripe_ids_and_amounts(self):
        off_a = ChefServiceOffering.objects.create(chef=self.chef, service_type='home_chef', title='A', active=True)
        # Active tier
        ChefServicePriceTier.objects.create(
            offering=off_a,
            household_min=1,
            household_max=2,
            currency='usd',
            desired_unit_amount_cents=4000,
            active=True,
        )

        # Offering with no active tiers should be hidden
        off_b = ChefServiceOffering.objects.create(chef=self.chef, service_type='home_chef', title='B', active=True)

        url = reverse('service_offerings')
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertEqual(len(items), 1)
        tiers = items[0].get('tiers') or []
        self.assertTrue(all('stripe_price_id' not in t for t in tiers))
        self.assertTrue(all('desired_unit_amount_cents' not in t for t in tiers))
