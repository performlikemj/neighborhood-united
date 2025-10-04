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

    def test_update_price_marks_pending(self):
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"desired_unit_amount_cents": 4500}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.desired_unit_amount_cents, 4500)
        self.assertEqual(self.tier.price_sync_status, 'pending')
        self.assertIsNone(self.tier.last_price_sync_error)

    def test_cannot_set_stripe_price_id_directly(self):
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"stripe_price_id": "price_hacker"}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.tier.refresh_from_db()
        self.assertNotEqual(self.tier.stripe_price_id, "price_hacker")

    @patch('chef_services.views.sync_pending_service_tiers')
    def test_add_tier_triggers_sync_task(self, mock_sync_task):
        mock_sync_task.delay.return_value = None
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
        mock_sync_task.delay.assert_called_once()

    @patch('chef_services.views.sync_pending_service_tiers')
    def test_update_tier_triggers_sync_task_when_price_changes(self, mock_sync_task):
        mock_sync_task.delay.return_value = None
        url = reverse('service_tier_update', args=[self.tier.id])
        resp = self.client.patch(url, {"desired_unit_amount_cents": 5000}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        mock_sync_task.delay.assert_called_once()
