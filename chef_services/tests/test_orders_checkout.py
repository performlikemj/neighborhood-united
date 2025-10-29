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

    @patch('chef_services.payments.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_sub', url='https://session/sub'))
    def test_subscription_checkout_omits_payment_intent_data(self, mock_create):
        self.tier.is_recurring = True
        self.tier.recurrence_interval = 'week'
        self.tier.save(update_fields=['is_recurring', 'recurrence_interval'])

        order_payload = {
            "offering_id": self.off.id,
            "tier_id": self.tier.id,
            "household_size": 2,
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "12:00:00",
            "address_id": self.addr.id,
        }
        order_resp = self.client.post(reverse('service_create_order'), order_payload, format='json')
        self.assertEqual(order_resp.status_code, 201, order_resp.content)
        order_id = order_resp.json()['id']

        checkout_resp = self.client.post(reverse('service_checkout_order', args=[order_id]), {}, format='json')
        self.assertEqual(checkout_resp.status_code, 200, checkout_resp.content)

        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs.get('mode'), 'subscription')
        self.assertIn('subscription_data', kwargs)
        self.assertNotIn('payment_intent_data', kwargs)

    @patch('chef_services.payments.stripe.checkout.Session.retrieve', return_value=SimpleNamespace(id='cs_456', url='https://retrieved/session'))
    @patch('chef_services.payments.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_456', url=None))
    def test_checkout_fetches_session_url_when_missing(self, mock_create, mock_retrieve):
        order_payload = {
            "offering_id": self.off.id,
            "household_size": 2,
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "10:00:00",
            "address_id": self.addr.id,
        }
        order_resp = self.client.post(reverse('service_create_order'), order_payload, format='json')
        self.assertEqual(order_resp.status_code, 201, order_resp.content)
        order_id = order_resp.json()['id']

        resp = self.client.post(reverse('service_checkout_order', args=[order_id]), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        self.assertTrue(payload.get('success'))
        self.assertEqual(payload.get('session_url'), 'https://retrieved/session')
        mock_create.assert_called_once()
        mock_retrieve.assert_called_once_with('cs_456')

    def test_chef_can_list_their_orders(self):
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            service_date=timezone.now().date(),
            service_start_time=timezone.now().time(),
        )

        # Authenticate as chef
        self.client.force_authenticate(user=self.chef_user)
        resp = self.client.get(reverse('service_my_orders'))
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], order.id)
        self.assertEqual(payload[0]['customer'], self.user.id)

    def test_non_chef_cannot_list_orders(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(reverse('service_my_orders'))
        self.assertEqual(resp.status_code, 403)

    def test_confirmed_order_checkout_returns_success_without_session(self):
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            service_date=timezone.now().date(),
            service_start_time=timezone.now().time(),
            status='confirmed',
        )

        url = reverse('service_checkout_order', args=[order.id])
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('already_paid'))
        self.assertEqual(data.get('status'), 'confirmed')

    def test_create_draft_order_without_scheduling_details(self):
        """Test that draft orders can be created without scheduling details (add to cart)"""
        url = reverse('service_create_order')
        payload = {
            "offering_id": self.off.id,
            "household_size": 2,
            # Note: No service_date, service_start_time, or address_id
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['status'], 'draft')
        self.assertIsNone(data.get('service_date'))
        self.assertIsNone(data.get('service_start_time'))

    def test_checkout_fails_without_scheduling_details(self):
        """Test that checkout fails when required scheduling details are missing"""
        # Create draft order without scheduling details
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            status='draft',
        )

        url = reverse('service_checkout_order', args=[order.id])
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn('validation_errors', data)
        self.assertIn('service_date', data['validation_errors'])
        self.assertIn('service_start_time', data['validation_errors'])
        self.assertIn('address', data['validation_errors'])

    def test_update_draft_order_with_scheduling_details(self):
        """Test updating a draft order with scheduling details"""
        # Create draft order without scheduling
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            status='draft',
        )

        url = reverse('service_update_order', args=[order.id])
        payload = {
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "14:00:00",
            "address_id": self.addr.id,
            "special_requests": "Please use the back entrance"
        }
        resp = self.client.patch(url, payload, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['service_date'], timezone.now().date().isoformat())
        self.assertEqual(data['service_start_time'], "14:00:00")
        self.assertEqual(data['special_requests'], "Please use the back entrance")

    def test_cannot_update_non_draft_order(self):
        """Test that only draft orders can be updated"""
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            service_date=timezone.now().date(),
            service_start_time=timezone.now().time(),
            status='confirmed',
        )

        url = reverse('service_update_order', args=[order.id])
        payload = {
            "service_date": (timezone.now().date() + timezone.timedelta(days=1)).isoformat(),
        }
        resp = self.client.patch(url, payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Cannot update order with status', resp.json()['error'])

    @patch('chef_services.payments.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_789', url='https://session'))
    def test_full_workflow_draft_to_checkout(self, _mock_create):
        """Test complete workflow: create draft, update with details, checkout"""
        # Step 1: Create draft order
        create_url = reverse('service_create_order')
        create_payload = {
            "offering_id": self.off.id,
            "household_size": 2,
        }
        create_resp = self.client.post(create_url, create_payload, format='json')
        self.assertEqual(create_resp.status_code, 201, create_resp.content)
        order_id = create_resp.json()['id']

        # Step 2: Update with scheduling details
        update_url = reverse('service_update_order', args=[order_id])
        update_payload = {
            "service_date": timezone.now().date().isoformat(),
            "service_start_time": "14:00:00",
            "address_id": self.addr.id,
        }
        update_resp = self.client.patch(update_url, update_payload, format='json')
        self.assertEqual(update_resp.status_code, 200, update_resp.content)

        # Step 3: Checkout
        checkout_url = reverse('service_checkout_order', args=[order_id])
        checkout_resp = self.client.post(checkout_url, {}, format='json')
        self.assertEqual(checkout_resp.status_code, 200, checkout_resp.content)
        data = checkout_resp.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('session_id'), 'cs_789')

    def test_customer_can_list_their_orders(self):
        """Test that customers can list their own service orders"""
        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            status='draft',
        )

        url = reverse('service_my_customer_orders')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], order.id)
        self.assertEqual(data[0]['status'], 'draft')
