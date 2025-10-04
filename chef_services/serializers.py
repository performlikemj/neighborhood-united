from rest_framework import serializers
from .models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder


class ChefServicePriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefServicePriceTier
        fields = [
            'id', 'offering', 'household_min', 'household_max', 'currency',
            'desired_unit_amount_cents',
            'is_recurring', 'recurrence_interval', 'active', 'display_label',
            'stripe_price_id', 'price_sync_status', 'last_price_sync_error', 'price_synced_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'offering', 'stripe_price_id', 'price_sync_status', 'last_price_sync_error', 'price_synced_at']

    def validate(self, data):
        # Leverage model.clean via is_valid + instance creation in views
        return data


class ChefServiceOfferingSerializer(serializers.ModelSerializer):
    tiers = ChefServicePriceTierSerializer(many=True, read_only=True)

    class Meta:
        model = ChefServiceOffering
        fields = [
            'id', 'chef', 'service_type', 'title', 'description', 'active',
            'default_duration_minutes', 'max_travel_miles', 'notes',
            'created_at', 'updated_at', 'tiers'
        ]
        read_only_fields = ['chef', 'created_at', 'updated_at', 'tiers']


class ChefServiceOrderSerializer(serializers.ModelSerializer):
    offering_title = serializers.CharField(source='offering.title', read_only=True)
    service_type = serializers.CharField(source='offering.service_type', read_only=True)
    chef_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChefServiceOrder
        fields = [
            'id', 'customer', 'chef', 'offering', 'tier', 'household_size',
            'service_date', 'service_start_time', 'duration_minutes', 'address', 'special_requests',
            'schedule_preferences',
            'stripe_session_id', 'stripe_subscription_id', 'is_subscription',
            'status', 'created_at', 'updated_at',
            'offering_title', 'service_type', 'chef_id'
        ]
        read_only_fields = ['customer', 'chef', 'stripe_session_id', 'stripe_subscription_id', 'is_subscription', 'status', 'created_at', 'updated_at']


# Public variants to avoid exposing stripe_price_id in discovery endpoints
class PublicChefServicePriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefServicePriceTier
        fields = [
            'id', 'household_min', 'household_max', 'currency',
            'is_recurring', 'recurrence_interval', 'active', 'display_label',
        ]


class PublicChefServiceOfferingSerializer(serializers.ModelSerializer):
    tiers = PublicChefServicePriceTierSerializer(many=True, read_only=True)

    class Meta:
        model = ChefServiceOffering
        fields = [
            'id', 'chef', 'service_type', 'title', 'description', 'active',
            'default_duration_minutes', 'max_travel_miles', 'notes',
            'created_at', 'updated_at', 'tiers'
        ]
        read_only_fields = ['chef', 'created_at', 'updated_at', 'tiers']
