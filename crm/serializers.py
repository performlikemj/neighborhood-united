from rest_framework import serializers

from .models import Lead, LeadInteraction


class UserSummaryField(serializers.RelatedField):
    def to_representation(self, value):
        if value is None:
            return None
        return {
            "id": value.pk,
            "name": value.get_full_name() or value.get_username(),
        }


class LeadInteractionSerializer(serializers.ModelSerializer):
    author = UserSummaryField(read_only=True)
    interaction_type_display = serializers.CharField(
        source="get_interaction_type_display", read_only=True
    )

    class Meta:
        model = LeadInteraction
        fields = [
            "id",
            "interaction_type",
            "interaction_type_display",
            "summary",
            "details",
            "happened_at",
            "next_steps",
            "author",
        ]
        read_only_fields = ["id", "author"]


class LeadSerializer(serializers.ModelSerializer):
    owner = UserSummaryField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    interactions = LeadInteractionSerializer(many=True, read_only=True)
    next_action = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "company",
            "status",
            "status_display",
            "source",
            "source_display",
            "is_priority",
            "budget_cents",
            "notes",
            "offering",
            "owner",
            "last_interaction_at",
            "interactions",
            "next_action",
        ]
        read_only_fields = ["id", "owner", "last_interaction_at"]

    def get_next_action(self, obj):
        interaction = obj.interactions.filter(next_steps__isnull=False).exclude(next_steps="").first()
        if not interaction:
            return None
        return {
            "next_steps": interaction.next_steps,
            "scheduled_at": interaction.happened_at,
        }
