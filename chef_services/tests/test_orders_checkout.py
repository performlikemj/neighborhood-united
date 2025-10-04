from types import SimpleNamespace
from unittest.mock import patch

from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from django.utils import timezone

from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder
from meals.models import StripeConnectAccount


class ChefServicesOrdersCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username="u1", email="u1@example.com", password="pass")
        self.chef_user = CustomUser.objects.create_user(username="chef", email="chef@example.com", password="pass")
        self.chef = Chef.objects.create(user=self.chef_user)
        StripeConnectAccount.objects.create(chef=self.chef, stripe_account_id='acct_123', is_active=True)
        self.account_patcher = patch(
            'meals.utils.stripe_utils.stripe.Account.retrieve',
            return_value=SimpleNamespace(charges_enabled=True, payouts_enabled=True, details_submitted=True),
        )
        self.account_patcher.start()
        # Address for user
        self.addr = Address.objects.create(user=self.user, street="1 A St")
        self.off = ChefServiceOffering.objects.create(chef=self.chef, service_type='home_chef', title='Home', active=True)
        self.tier = ChefServicePriceTier.objects.create(
            offering=self.off,
            household_min=1,
            household_max=4,
            currency='usd',
            desired_unit_amount_cents=5000,
            active=True,
            stripe_price_id='price_abc',
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.account_patcher.stop()

    def test_create_order_and_auto_select_tier(self):
        url = reverse('service_create_order')
        payload = {
            "offering_id": self.off.id,
            "household_size": 2,
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "10:00:00",
            "address_id": self.addr.id,
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['tier'], self.tier.id)

    def test_create_order_rejects_address_of_another_user(self):
        other = CustomUser.objects.create_user(username="u2", email="u2@example.com", password="pass")
        other_addr = Address.objects.create(user=other, street="2 B St")
        url = reverse('service_create_order')
        payload = {
            "offering_id": self.off.id,
            "household_size": 2,
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "10:00:00",
            "address_id": other_addr.id,
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 403)

    @patch('chef_services.payments.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_123', url='https://session'))
    def test_checkout_session_created(self, _mock_create):
        # Create order
        order_url = reverse('service_create_order')
        payload = {
            "offering_id": self.off.id,
            "household_size": 2,
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "10:00:00",
            "address_id": self.addr.id,
        }
        resp = self.client.post(order_url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        order_id = resp.json()['id']

        url = reverse('service_checkout_order', args=[order_id])
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('session_id'), 'cs_123')

    @patch('chef_services.views.stripe.checkout.Session.retrieve', return_value=SimpleNamespace(id='cs_123', url='https://session'))
    def test_checkout_reuses_existing_session_when_awaiting_payment(self, _mock_retrieve):
        # Create order then mark awaiting
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            service_date=timezone.now().date(),
            service_start_time=timezone.now().time(),
            status='awaiting_payment',
            stripe_session_id='cs_123',
        )
        url = reverse('service_checkout_order', args=[order.id])
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('session_id'), 'cs_123')
