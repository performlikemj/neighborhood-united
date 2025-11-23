from rest_framework import serializers

from .models import ServiceOffering, ServiceTier


class ServiceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceTier
        fields = [
            "id",
            "name",
            "description",
            "price_cents",
            "billing_cycle",
            "min_commitment_weeks",
            "max_clients",
            "sort_order",
            "is_active",
        ]
        read_only_fields = ["id"]


class ServiceOfferingSerializer(serializers.ModelSerializer):
    tiers = ServiceTierSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = ServiceOffering
        fields = [
            "id",
            "name",
            "slug",
            "summary",
            "description",
            "category",
            "category_display",
            "is_active",
            "is_deleted",
            "tiers",
        ]
        read_only_fields = ["id", "is_deleted"]
