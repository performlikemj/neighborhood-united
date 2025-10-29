from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier
from chef_services.tasks import sync_pending_service_tiers


class SyncPendingServiceTiersTests(TestCase):
    def setUp(self):
        user = CustomUser.objects.create_user(
            username="chef",
            email="chef@example.com",
            password="pass123",
            first_name="Marcus",
            last_name="Garvey",
        )
        self.chef = Chef.objects.create(user=user)
        self.offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="Private Dinner",
            active=True,
        )

    @patch("chef_services.tasks.stripe")
    def test_creates_stripe_price_for_pending_tier(self, mock_stripe):
        mock_stripe.Product.create.return_value = MagicMock(id="prod_123")
        mock_price = MagicMock(id="price_123", unit_amount=15000, currency="usd", recurring=None)
        mock_stripe.Price.create.return_value = mock_price

        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=15000,
            is_recurring=False,
            active=True,
            price_sync_status="pending",
        )

        result = sync_pending_service_tiers()
        self.assertIn("processed", result)

        tier.refresh_from_db()
        self.assertEqual(tier.stripe_price_id, "price_123")
        self.assertEqual(tier.price_sync_status, "success")
        self.assertIsNotNone(tier.price_synced_at)
        mock_stripe.Product.create.assert_called_once()
        product_kwargs = mock_stripe.Product.create.call_args.kwargs
        expected_name = "Private Dinner – Marcus Garvey"
        self.assertEqual(product_kwargs["name"], expected_name)
        mock_stripe.Price.create.assert_called_once()

    @patch("chef_services.tasks.stripe")
    def test_reuses_existing_price_when_matching(self, mock_stripe):
        self.offering.stripe_product_id = "prod_existing"
        self.offering.save(update_fields=["stripe_product_id"])

        mock_price = SimpleNamespace(unit_amount=5000, currency="usd", recurring=None)
        mock_stripe.Price.retrieve.return_value = mock_price

        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=2,
            currency="usd",
            desired_unit_amount_cents=5000,
            is_recurring=False,
            active=True,
            price_sync_status="pending",
            stripe_price_id="price_existing",
        )

        result = sync_pending_service_tiers()
        self.assertIn("processed", result)

        tier.refresh_from_db()
        self.assertEqual(tier.stripe_price_id, "price_existing")
        self.assertEqual(tier.price_sync_status, "success")
        self.assertIsNone(tier.last_price_sync_error)
        mock_stripe.Product.create.assert_not_called()
        mock_stripe.Price.create.assert_not_called()
        mock_stripe.Price.retrieve.assert_called_once_with("price_existing")
