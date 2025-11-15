from django.urls import reverse
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ChefCustomerConnectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomUser.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="pass",
        )
        self.customer_two = CustomUser.objects.create_user(
            username="other",
            email="other@example.com",
            password="pass",
        )
        self.chef_user = CustomUser.objects.create_user(
            username="chef",
            email="chef@example.com",
            password="pass",
        )
        self.chef = Chef.objects.create(user=self.chef_user)

    def _authenticate(self, user=None):
        if user is None:
            self.client.force_authenticate(user=None)
        else:
            self.client.force_authenticate(user=user)

    def test_customer_connection_request_and_chef_accept_flow(self):
        connections_url = reverse('service_connections')

        # Customer initiates connection
        self._authenticate(self.customer)
        resp = self.client.post(connections_url, {"chef_id": self.chef.id}, format='json', secure=True)
        self.assertEqual(resp.status_code, 201)
        payload = resp.json()
        self.assertEqual(payload['status'], 'pending')
        self.assertEqual(payload['initiated_by'], 'customer')
        connection_id = payload['id']

        # Chef sees pending connection
        self._authenticate(self.chef_user)
        resp = self.client.get(connections_url, secure=True)
        self.assertEqual(resp.status_code, 200)
        listings = resp.json()
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]['status'], 'pending')

        # Chef accepts connection
        detail_url = reverse('service_connection_detail', args=[connection_id])
        resp = self.client.patch(detail_url, {"action": "accept"}, format='json', secure=True)
        self.assertEqual(resp.status_code, 200)
        accepted = resp.json()
        self.assertEqual(accepted['status'], 'accepted')

        # Customer now sees accepted connection
        self._authenticate(self.customer)
        resp = self.client.get(connections_url, secure=True)
        self.assertEqual(resp.status_code, 200)
        final_listing = resp.json()
        self.assertEqual(len(final_listing), 1)
        self.assertEqual(final_listing[0]['status'], 'accepted')

    def test_personalized_offering_hidden_from_unconnected_users(self):
        connections_url = reverse('service_connections')

        # Customer requests connection and chef accepts
        self._authenticate(self.customer)
        resp = self.client.post(connections_url, {"chef_id": self.chef.id}, format='json', secure=True)
        self.assertEqual(resp.status_code, 201)
        connection_id = resp.json()['id']

        self._authenticate(self.chef_user)
        detail_url = reverse('service_connection_detail', args=[connection_id])
        resp = self.client.patch(detail_url, {"action": "accept"}, format='json', secure=True)
        self.assertEqual(resp.status_code, 200)

        # Chef creates a personalized offering tied to the connected customer
        offerings_url = reverse('service_offerings')
        create_payload = {
            "service_type": "home_chef",
            "title": "Private Dinner",
            "description": "One-on-one",
            "target_customer_ids": [self.customer.id],
        }
        resp = self.client.post(offerings_url, create_payload, format='json', secure=True)
        self.assertEqual(resp.status_code, 201)
        offering_id = resp.json()['id']

        # Add a price tier to make offering discoverable
        offering = ChefServiceOffering.objects.get(id=offering_id)
        ChefServicePriceTier.objects.create(
            offering=offering,
            household_min=1,
            household_max=2,
            currency='usd',
            desired_unit_amount_cents=10000,
            active=True,
        )

        # Unconnected user cannot see personalized offering
        self._authenticate(self.customer_two)
        resp = self.client.get(offerings_url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

        # Targeted customer can see offering
        self._authenticate(self.customer)
        resp = self.client.get(offerings_url, secure=True)
        self.assertEqual(resp.status_code, 200)
        visible = resp.json()
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]['id'], offering_id)

        # Anonymous visitor cannot see personalized offering
        self._authenticate(None)
        resp = self.client.get(offerings_url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_missing_payload_logs_warning(self):
        connections_url = reverse('service_connections')
        self._authenticate(self.customer)
        with self.assertLogs('chef_services.views', level='WARNING') as captured:
            resp = self.client.post(connections_url, {}, format='json', secure=True)
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(any('chef_id is required' in message for message in captured.output))
