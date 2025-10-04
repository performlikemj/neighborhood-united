from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder
from chef_services.tasks import sync_pending_service_tiers
from chef_services.webhooks import handle_checkout_session_completed


class ChefServicesWebhooksSyncTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username="u1", email="u1@example.com", password="pass")
        self.chef_user = CustomUser.objects.create_user(username="chef", email="chef@example.com", password="pass")
        self.chef = Chef.objects.create(user=self.chef_user)
        self.off = ChefServiceOffering.objects.create(chef=self.chef, service_type='weekly_prep', title='Weekly', active=True)
        self.tier = ChefServicePriceTier.objects.create(
            offering=self.off,
            household_min=1,
            household_max=4,
            currency='usd',
            desired_unit_amount_cents=5000,
            active=True,
            is_recurring=True,
            recurrence_interval='week',
        )

    @patch('chef_services.tasks.stripe.Product.create', return_value=SimpleNamespace(id='prod_123'))
    @patch('chef_services.tasks.stripe.Price.create', return_value=SimpleNamespace(id='price_123', unit_amount=5000, currency='usd', recurring=SimpleNamespace(interval='week')))
    def test_sync_task_creates_product_and_price(self, _mock_price_create, _mock_prod_create):
        result = sync_pending_service_tiers()
        self.tier.refresh_from_db()
        self.off.refresh_from_db()
        self.assertEqual(self.off.stripe_product_id, 'prod_123')
        self.assertEqual(self.tier.stripe_price_id, 'price_123')
        self.assertEqual(self.tier.price_sync_status, 'success')
        self.assertIsNotNone(self.tier.price_synced_at)

    @patch('chef_services.webhooks.stripe.checkout.Session.retrieve')
    def test_webhook_confirms_order_after_verification(self, mock_retrieve):
        # Pretend sync already created a price
        self.tier.stripe_price_id = 'price_123'
        self.tier.save(update_fields=['stripe_price_id'])

        order = ChefServiceOrder.objects.create(
            customer=self.user,
            chef=self.chef,
            offering=self.off,
            tier=self.tier,
            household_size=2,
            service_date=timezone.now().date(),
            service_start_time=timezone.now().time(),
            status='awaiting_payment',
        )

        # Mock expanded session retrieval to validate mode and price id
        mock_retrieve.return_value = SimpleNamespace(
            id='cs_123',
            mode='subscription',
            line_items=SimpleNamespace(data=[SimpleNamespace(price=SimpleNamespace(id='price_123'))])
        )

        session = SimpleNamespace(
            id='cs_123',
            metadata={'order_type': 'service', 'service_order_id': str(order.id), 'tier_id': str(self.tier.id)},
            subscription='sub_123',
        )
        handle_checkout_session_completed(session)

        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(order.stripe_subscription_id, 'sub_123')

