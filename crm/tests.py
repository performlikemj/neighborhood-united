from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from crm.models import Lead, LeadInteraction
from crm.serializers import LeadSerializer
from services.models import ServiceOffering


class LeadSerializerTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="pw")
        self.author = user_model.objects.create_user(username="author", password="pw")
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


class LeadInteractionSaveTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author = user_model.objects.create_user(username="author", password="pw")
        self.lead = Lead.objects.create(first_name="Latest")

    def test_backdated_interaction_does_not_override_newer_activity(self):
        latest_time = timezone.now()
        older_time = latest_time - timedelta(days=1)

        LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.NOTE,
            summary="Most recent",
            happened_at=latest_time,
        )

        LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.NOTE,
            summary="Backdated",
            happened_at=older_time,
        )

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.last_interaction_at, latest_time)

    def test_updating_older_interaction_keeps_latest_timestamp(self):
        latest_time = timezone.now()
        older_time = latest_time - timedelta(hours=2)

        LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.CALL,
            summary="Call",
            happened_at=latest_time,
        )
        older = LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.NOTE,
            summary="Note",
            happened_at=older_time,
        )

        older.happened_at = older_time - timedelta(days=1)
        older.save()

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.last_interaction_at, latest_time)

    def test_deleting_latest_recomputes_to_next_newest(self):
        newest_time = timezone.now()
        older_time = newest_time - timedelta(hours=1)

        newest = LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.EMAIL,
            summary="Newest",
            happened_at=newest_time,
        )
        LeadInteraction.objects.create(
            lead=self.lead,
            author=self.author,
            interaction_type=LeadInteraction.InteractionType.NOTE,
            summary="Older",
            happened_at=older_time,
        )

        newest.is_deleted = True
        newest.save()

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.last_interaction_at, older_time)
