from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient

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

