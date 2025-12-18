from django.test import TestCase, SimpleTestCase

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier
from chef_services.serializers import (
    ChefServiceOfferingSerializer,
    PublicChefServiceOfferingSerializer,
    _format_amount,
    build_tier_summary,
)


class ChefServiceOfferingSerializerTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="chef_tester",
            email="chef@example.com",
            password="pass1234",
        )
        self.chef = Chef.objects.create(user=self.user)

    def _build_offering_with_tiers(self):
        offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="Tasting Menu",
            description="Test description",
            active=True,
        )
        ChefServicePriceTier.objects.create(
            offering=offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=12000,
            is_recurring=False,
            active=True,
            display_label="Couples & Small Families",
        )
        ChefServicePriceTier.objects.create(
            offering=offering,
            household_min=5,
            household_max=None,
            currency="usd",
            desired_unit_amount_cents=20000,
            is_recurring=True,
            recurrence_interval="week",
            active=True,
        )
        return offering

    def test_private_serializer_includes_helper_fields(self):
        offering = self._build_offering_with_tiers()

        data = ChefServiceOfferingSerializer(offering).data

        self.assertIn("service_type_label", data)
        self.assertEqual(data["service_type_label"], offering.get_service_type_display())
        self.assertIn("tier_summary", data)
        self.assertEqual(
            data["tier_summary"],
            [
                "Couples & Small Families: $120, one-time",
                "5+ people: $200, recurring weekly",
            ],
        )

    def test_public_serializer_includes_helper_fields(self):
        offering = self._build_offering_with_tiers()

        data = PublicChefServiceOfferingSerializer(offering).data

        self.assertIn("service_type_label", data)
        self.assertEqual(data["service_type_label"], offering.get_service_type_display())
        self.assertIn("tier_summary", data)
        self.assertEqual(
            data["tier_summary"],
            [
                "Couples & Small Families: $120, one-time",
                "5+ people: $200, recurring weekly",
            ],
        )


class CurrencyFormattingTests(SimpleTestCase):
    """Tests for _format_amount with different currencies. No database needed."""

    def test_format_usd_whole_dollars(self):
        """USD 5000 cents should display as $50."""
        result = _format_amount(5000, "usd")
        self.assertEqual(result, "$50")

    def test_format_usd_with_cents(self):
        """USD 5050 cents should display as $50.50."""
        result = _format_amount(5050, "usd")
        self.assertEqual(result, "$50.5")

    def test_format_usd_trailing_zeros_stripped(self):
        """USD should strip trailing zeros."""
        result = _format_amount(5000, "usd")
        self.assertNotIn(".00", result)
        self.assertEqual(result, "$50")

    def test_format_jpy_whole_units(self):
        """JPY 5000 should display as ¥5,000 (not ¥50)."""
        result = _format_amount(5000, "jpy")
        self.assertEqual(result, "¥5,000")

    def test_format_jpy_large_amount(self):
        """JPY 500000 should display as ¥500,000."""
        result = _format_amount(500000, "jpy")
        self.assertEqual(result, "¥500,000")

    def test_format_jpy_small_amount(self):
        """JPY 50 should display as ¥50."""
        result = _format_amount(50, "jpy")
        self.assertEqual(result, "¥50")

    def test_format_eur(self):
        """EUR 5000 cents should display as €50."""
        result = _format_amount(5000, "eur")
        self.assertEqual(result, "€50")

    def test_format_gbp(self):
        """GBP 3000 pence should display as £30."""
        result = _format_amount(3000, "gbp")
        self.assertEqual(result, "£30")

    def test_format_cad(self):
        """CAD 5000 cents should display as CA$50."""
        result = _format_amount(5000, "cad")
        self.assertEqual(result, "CA$50")

    def test_format_unknown_currency(self):
        """Unknown currency should use code as prefix."""
        result = _format_amount(5000, "xyz")
        self.assertEqual(result, "XYZ 50")

    def test_format_none_amount(self):
        """None amount should return 'Price TBD'."""
        result = _format_amount(None, "usd")
        self.assertEqual(result, "Price TBD")

    def test_format_uppercase_currency_code(self):
        """Uppercase currency code should work."""
        result = _format_amount(5000, "USD")
        self.assertEqual(result, "$50")

    def test_format_usd_with_thousands(self):
        """Large USD amounts should have comma separators."""
        result = _format_amount(100000, "usd")
        self.assertEqual(result, "$1,000")


class TierSummaryTests(TestCase):
    """Tests for build_tier_summary with different currencies."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="chef_summary", email="summary@example.com", password="pass"
        )
        self.chef = Chef.objects.create(user=self.user)
        self.offering = ChefServiceOffering.objects.create(
            chef=self.chef,
            service_type="home_chef",
            title="Summary Test",
            active=True,
        )

    def test_tier_summary_usd_one_time(self):
        """USD one-time tier summary."""
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,
            is_recurring=False,
            active=True,
        )
        summary = build_tier_summary(tier)
        self.assertEqual(summary, "1-4 people: $50, one-time")

    def test_tier_summary_jpy_one_time(self):
        """JPY one-time tier summary should show full yen amount."""
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="jpy",
            desired_unit_amount_cents=5000,  # ¥5000
            is_recurring=False,
            active=True,
        )
        summary = build_tier_summary(tier)
        self.assertEqual(summary, "1-4 people: ¥5,000, one-time")

    def test_tier_summary_jpy_large_amount(self):
        """JPY large amount should format correctly."""
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=5,
            household_max=None,
            currency="jpy",
            desired_unit_amount_cents=500000,  # ¥500,000
            is_recurring=False,
            active=True,
        )
        summary = build_tier_summary(tier)
        self.assertEqual(summary, "5+ people: ¥500,000, one-time")

    def test_tier_summary_recurring_weekly(self):
        """Recurring weekly tier summary."""
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=2,
            currency="usd",
            desired_unit_amount_cents=10000,
            is_recurring=True,
            recurrence_interval="week",
            active=True,
        )
        summary = build_tier_summary(tier)
        self.assertEqual(summary, "1-2 people: $100, recurring weekly")

    def test_tier_summary_with_display_label(self):
        """Custom display label should be used."""
        tier = ChefServicePriceTier.objects.create(
            offering=self.offering,
            household_min=1,
            household_max=4,
            currency="usd",
            desired_unit_amount_cents=5000,
            is_recurring=False,
            active=True,
            display_label="Small Family",
        )
        summary = build_tier_summary(tier)
        self.assertEqual(summary, "Small Family: $50, one-time")
