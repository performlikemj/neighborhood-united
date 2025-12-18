"""Tests for the currencies API endpoint and tier creation with currency validation."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier


class SupportedCurrenciesEndpointTests(TestCase):
    """Tests for GET /services/currencies/ endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_currencies_endpoint_returns_list(self):
        """Endpoint should return a list of supported currencies."""
        response = self.client.get('/services/currencies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('currencies', response.data)
        self.assertIsInstance(response.data['currencies'], list)

    def test_currencies_include_required_fields(self):
        """Each currency should have code, symbol, name, min_amount, min_display, zero_decimal."""
        response = self.client.get('/services/currencies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        for currency in response.data['currencies']:
            self.assertIn('code', currency)
            self.assertIn('symbol', currency)
            self.assertIn('name', currency)
            self.assertIn('min_amount', currency)
            self.assertIn('min_display', currency)
            self.assertIn('zero_decimal', currency)

    def test_jpy_is_zero_decimal(self):
        """JPY should be marked as zero_decimal."""
        response = self.client.get('/services/currencies/')
        jpy = next((c for c in response.data['currencies'] if c['code'] == 'jpy'), None)
        self.assertIsNotNone(jpy)
        self.assertTrue(jpy['zero_decimal'])
        self.assertEqual(jpy['symbol'], '¥')

    def test_usd_is_not_zero_decimal(self):
        """USD should NOT be zero_decimal."""
        response = self.client.get('/services/currencies/')
        usd = next((c for c in response.data['currencies'] if c['code'] == 'usd'), None)
        self.assertIsNotNone(usd)
        self.assertFalse(usd['zero_decimal'])
        self.assertEqual(usd['symbol'], '$')

    def test_currencies_sorted_by_code(self):
        """Currencies should be sorted alphabetically by code."""
        response = self.client.get('/services/currencies/')
        codes = [c['code'] for c in response.data['currencies']]
        self.assertEqual(codes, sorted(codes))

    def test_endpoint_allows_anonymous_access(self):
        """Endpoint should be accessible without authentication."""
        # Don't authenticate
        response = self.client.get('/services/currencies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TierCreationCurrencyValidationTests(TestCase):
    """Tests for tier creation with currency validation via API."""

    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username="chef_api", email="chef_api@example.com", password="pass123"
        )
        self.chef = Chef.objects.create(user=self.user)
        self.offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="API Test Offering",
            active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_create_tier_valid_usd(self):
        """Creating a tier with valid USD should succeed."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 1,
                'household_max': 4,
                'currency': 'usd',
                'desired_unit_amount_cents': 5000,
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['currency'], 'usd')

    def test_create_tier_valid_jpy(self):
        """Creating a tier with valid JPY should succeed."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 1,
                'household_max': 4,
                'currency': 'jpy',
                'desired_unit_amount_cents': 5000,
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['currency'], 'jpy')

    def test_create_tier_invalid_currency_rejected(self):
        """Creating a tier with invalid currency should fail."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 1,
                'household_max': 4,
                'currency': 'xyz',
                'desired_unit_amount_cents': 5000,
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_tier_usd_below_minimum_rejected(self):
        """Creating USD tier below minimum amount should fail."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 1,
                'household_max': 4,
                'currency': 'usd',
                'desired_unit_amount_cents': 40,  # Below $0.50 minimum
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_tier_jpy_below_minimum_rejected(self):
        """Creating JPY tier below minimum amount should fail."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 1,
                'household_max': 4,
                'currency': 'jpy',
                'desired_unit_amount_cents': 30,  # Below ¥50 minimum
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_tier_uppercase_currency_normalized(self):
        """Uppercase currency code should be normalized to lowercase."""
        response = self.client.post(
            f'/services/offerings/{self.offering.id}/tiers/',
            {
                'household_min': 5,
                'household_max': None,
                'currency': 'USD',  # Uppercase
                'desired_unit_amount_cents': 10000,
                'is_recurring': False,
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['currency'], 'usd')  # Normalized
