from django.test import TestCase

from services.models import ServiceOffering, ServiceTier
from services.serializers import ServiceOfferingSerializer


class ServiceOfferingSerializerTests(TestCase):
    def setUp(self):
        self.offering = ServiceOffering.objects.create(
            name="Weekly Chef",
            slug="weekly-chef",
            summary="In-home support",
            category=ServiceOffering.Category.MEAL_PREP,
        )
        self.tier_one = ServiceTier.objects.create(
            offering=self.offering,
            name="Starter",
            price_cents=15000,
            billing_cycle=ServiceTier.BillingCycle.WEEKLY,
            sort_order=2,
        )
        self.tier_two = ServiceTier.objects.create(
            offering=self.offering,
            name="Premium",
            price_cents=25000,
            billing_cycle=ServiceTier.BillingCycle.WEEKLY,
            sort_order=1,
        )

    def test_serializer_includes_nested_tiers(self):
        data = ServiceOfferingSerializer(self.offering).data
        tier_names = [tier["name"] for tier in data["tiers"]]
        self.assertEqual(["Premium", "Starter"], tier_names)


class ServiceOfferingQuerySetTests(TestCase):
    def test_active_queryset_excludes_soft_deleted(self):
        active = ServiceOffering.objects.create(
            name="Events",
            slug="events",
            category=ServiceOffering.Category.EVENTS,
        )
        ServiceOffering.objects.create(
            name="Archived",
            slug="archived",
            category=ServiceOffering.Category.EVENTS,
            is_active=False,
        )
        ServiceOffering.objects.create(
            name="Deleted",
            slug="deleted",
            category=ServiceOffering.Category.EVENTS,
            is_deleted=True,
        )

        qs = ServiceOffering.objects.active()
        self.assertEqual([active], list(qs))
