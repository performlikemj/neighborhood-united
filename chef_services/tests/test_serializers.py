from django.test import TestCase

from custom_auth.models import CustomUser
from chefs.models import Chef
from chef_services.models import ChefServiceOffering, ChefServicePriceTier
from chef_services.serializers import (
    ChefServiceOfferingSerializer,
    PublicChefServiceOfferingSerializer,
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
