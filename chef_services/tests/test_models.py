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

