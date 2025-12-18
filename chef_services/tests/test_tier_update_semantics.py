from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier


class ChefServicesTierUpdateSemanticsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.chef_user = CustomUser.objects.create_user(username="chef", email="chef@example.com", password="pass")
        self.chef = Chef.objects.create(user=self.chef_user)
        self.client.force_authenticate(user=self.chef_user)
        self.off = ChefServiceOffering.objects.create(chef=self.chef, service_type='home_chef', title='X', active=True)
        self.tier = ChefServicePriceTier.objects.create(
            offering=self.off,
            household_min=1,
            household_max=2,
            currency='usd',
            desired_unit_amount_cents=4000,
            active=True,
            price_sync_status='success'
        )

    @patch('chef_services.views._sync_tier_to_stripe')
    def test_update_price_triggers_sync(self, mock_sync):
        """Test that updating price triggers synchronous Stripe sync."""
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"desired_unit_amount_cents": 4500}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.desired_unit_amount_cents, 4500)
        # Sync is called synchronously
        mock_sync.assert_called_once()

    def test_cannot_set_stripe_price_id_directly(self):
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"stripe_price_id": "price_hacker"}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.tier.refresh_from_db()
        self.assertNotEqual(self.tier.stripe_price_id, "price_hacker")

    @patch('chef_services.views._sync_tier_to_stripe')
    def test_add_tier_triggers_sync(self, mock_sync):
        """Test that adding a tier triggers synchronous Stripe sync."""
        url = reverse('service_offering_add_tier', args=[self.off.id])
        payload = {
            "household_min": 3,
            "household_max": 6,
            "currency": "usd",
            "desired_unit_amount_cents": 5500,
            "is_recurring": False,
            "active": True,
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # Sync is called synchronously
        mock_sync.assert_called_once()

    @patch('chef_services.views._sync_tier_to_stripe')
    def test_update_tier_triggers_sync_when_price_changes(self, mock_sync):
        """Test that updating price-related fields triggers synchronous Stripe sync."""
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"desired_unit_amount_cents": 5000}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Sync is called synchronously
        mock_sync.assert_called_once()

    @patch('chef_services.views._sync_tier_to_stripe')
    def test_update_non_price_field_does_not_trigger_sync(self, mock_sync):
        """Test that updating non-price fields does NOT trigger Stripe sync."""
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"active": False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Sync should NOT be called for non-price changes
        mock_sync.assert_not_called()
