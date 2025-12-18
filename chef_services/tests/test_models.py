from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder


class ChefServiceModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="chef1", email="chef1@example.com", password="pass"
        )
        self.chef = Chef.objects.create(user=self.user)
        self.offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="Home Chef",
            active=True,
        )

    def test_active_tier_overlap_is_rejected(self):
        ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=2,
            currency="usd",
            desired_unit_amount_cents=5000,
            active=True,
        )
        tier2 = ChefServicePriceTier(
            offering=self.offering,
            household_min=2,  # overlaps at boundary with 1-2
            household_max=3,
            currency="usd",
            desired_unit_amount_cents=6000,
            active=True,
        )
        with self.assertRaises(ValidationError):
            tier2.full_clean()

    def test_inactive_overlap_allowed(self):
        ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,
            active=False,
        )
        tier2 = ChefServicePriceTier(
            offering=self.offering,
            household_min=2,
            household_max=3,
            currency="usd",
            desired_unit_amount_cents=6000,
            active=True,
        )
        # Should be OK because the overlapping one is inactive
        tier2.full_clean()

    def test_recurring_interval_consistency(self):
        t = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,
            is_recurring=True,
            recurrence_interval=None,
            active=True,
        )
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_order_schedule_validation(self):
        # home_chef requires service_date and service_start_time
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,
            active=True,
        )
        order = ChefServiceOrder(
            customer=self.user,
            chef=self.chef,
            offering=self.offering,
            tier=tier,
            household_size=2,
            # missing date/time
        )
        with self.assertRaises(ValidationError):
            order.full_clean()


class CurrencyValidationTests(TestCase):
    """Tests for currency validation in ChefServicePriceTier."""
    
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="chef_currency", email="currency@example.com", password="pass"
        )
        self.chef = Chef.objects.create(user=self.user)
        self.offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="Currency Test",
            active=True,
        )

    def test_valid_usd_currency(self):
        """USD should be accepted with proper minimum."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,  # $50.00
            active=True,
        )
        tier.full_clean()  # Should not raise
        tier.save()
        self.assertEqual(tier.currency, "usd")

    def test_valid_jpy_currency(self):
        """JPY should be accepted with proper minimum."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="jpy",
            desired_unit_amount_cents=5000,  # ¥5000
            active=True,
        )
        tier.full_clean()  # Should not raise
        tier.save()
        self.assertEqual(tier.currency, "jpy")

    def test_valid_eur_currency(self):
        """EUR should be accepted."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="eur",
            desired_unit_amount_cents=5000,  # €50.00
            active=True,
        )
        tier.full_clean()
        tier.save()
        self.assertEqual(tier.currency, "eur")

    def test_currency_normalized_to_lowercase(self):
        """Currency should be normalized to lowercase."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="USD",  # Uppercase
            desired_unit_amount_cents=5000,
            active=True,
        )
        tier.full_clean()
        self.assertEqual(tier.currency, "usd")  # Should be lowercase

    def test_invalid_currency_rejected(self):
        """Invalid currency code should raise ValidationError."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="xyz",  # Invalid
            desired_unit_amount_cents=5000,
            active=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            tier.full_clean()
        self.assertIn("currency", ctx.exception.message_dict)
        self.assertIn("Unsupported currency", str(ctx.exception))

    def test_usd_minimum_amount_enforced(self):
        """USD requires minimum 50 cents."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=40,  # Below $0.50 minimum
            active=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            tier.full_clean()
        self.assertIn("desired_unit_amount_cents", ctx.exception.message_dict)

    def test_jpy_minimum_amount_enforced(self):
        """JPY requires minimum ¥50."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="jpy",
            desired_unit_amount_cents=30,  # Below ¥50 minimum
            active=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            tier.full_clean()
        self.assertIn("desired_unit_amount_cents", ctx.exception.message_dict)

    def test_jpy_at_minimum_allowed(self):
        """JPY at exactly minimum should be allowed."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="jpy",
            desired_unit_amount_cents=50,  # Exactly ¥50 minimum
            active=True,
        )
        tier.full_clean()  # Should not raise

    def test_usd_at_minimum_allowed(self):
        """USD at exactly minimum should be allowed."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=50,  # Exactly $0.50 minimum
            active=True,
        )
        tier.full_clean()  # Should not raise

    def test_mxn_higher_minimum(self):
        """MXN has a higher minimum (1000 centavos = $10 MXN)."""
        tier = ChefServicePriceTier(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="mxn",
            desired_unit_amount_cents=500,  # Below MX$10 minimum
            active=True,
        )
        with self.assertRaises(ValidationError):
            tier.full_clean()
        
        # At minimum should work
        tier.desired_unit_amount_cents = 1000
        tier.full_clean()  # Should not raise

