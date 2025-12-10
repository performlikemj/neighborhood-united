from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from crm.models import Lead, LeadInteraction
from crm.serializers import LeadSerializer
from services.models import ServiceOffering


class LeadSerializerTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", email="owner@test.com", password="pw")
        self.author = user_model.objects.create_user(username="author", email="author@test.com", password="pw")
        self.offering = ServiceOffering.objects.create(
            name="Tasting Menu",
            slug="tasting-menu",
            category=ServiceOffering.Category.EVENTS,
        )
        self.lead = Lead.objects.create(
            first_name="Maya",
            last_name="Rivera",
            email="maya@example.com",
            owner=self.owner,
            offering=self.offering,
            status=Lead.Status.CONTACTED,
            source=Lead.Source.REFERRAL,
        )
        LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.CALL,
            summary="Discovery call",
            details="Talked through requirements",
            happened_at=timezone.now(),
        )

    def test_serializer_renders_nested_interactions(self):
        data = LeadSerializer(self.lead).data
        self.assertEqual(data["owner"]["id"], self.owner.id)
        self.assertEqual(data["status"], Lead.Status.CONTACTED)
        self.assertEqual(len(data["interactions"]), 1)
        self.assertEqual(data["interactions"][0]["interaction_type"], "call")


class LeadQuerySetTests(TestCase):
    def test_open_queryset_filters_status(self):
        lead_open = Lead.objects.create(first_name="Sam")
        Lead.objects.create(first_name="Closed", status=Lead.Status.WON)
        qs = Lead.objects.open()
        self.assertEqual([lead_open], list(qs))
