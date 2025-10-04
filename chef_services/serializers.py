from decimal import Decimal

from rest_framework import serializers

from .models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder


_CURRENCY_SYMBOLS = {
    "usd": "$",
    "cad": "CA$",
    "eur": "€",
    "gbp": "£",
    "jpy": "¥",
}


def _format_amount(amount_cents, currency_code):
    if amount_cents is None:
        return "Price TBD"

    amount = (Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.01"))
    if amount == amount.to_integral():
        amount_text = f"{int(amount):,}"
    else:
        amount_text = f"{amount:,.2f}".rstrip("0").rstrip(".")

    currency_lower = (currency_code or "").lower()
    symbol = _CURRENCY_SYMBOLS.get(currency_lower)
    if symbol:
        return f"{symbol}{amount_text}"
    return f"{currency_code.upper() if currency_code else 'CURRENCY'} {amount_text}"


def _format_household_label(tier):
    if tier.display_label:
        return tier.display_label

    if tier.household_max is None:
        return f"{tier.household_min}+ people"
    if tier.household_min == tier.household_max:
        return f"{tier.household_min} people"
    return f"{tier.household_min}-{tier.household_max} people"


def _format_recurrence(tier):
    if not tier.is_recurring:
        return "one-time"

    interval_map = {
        "week": "weekly",
        "month": "monthly",
    }
    interval = interval_map.get(tier.recurrence_interval or "", tier.recurrence_interval or "recurring")
    return f"recurring {interval}"


def build_tier_summary(tier):
    price_text = _format_amount(tier.desired_unit_amount_cents, tier.currency)
    recurrence_text = _format_recurrence(tier)
    return f"{_format_household_label(tier)}: {price_text}, {recurrence_text}"


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
    service_type_label = serializers.CharField(source='get_service_type_display', read_only=True)
    tier_summary = serializers.SerializerMethodField()

    class Meta:
        model = ChefServiceOffering
        fields = [
            'id', 'chef', 'service_type', 'title', 'description', 'active',
            'default_duration_minutes', 'max_travel_miles', 'notes',
            'created_at', 'updated_at', 'tiers', 'service_type_label', 'tier_summary'
        ]
        read_only_fields = ['chef', 'created_at', 'updated_at', 'tiers', 'service_type_label', 'tier_summary']

    def get_tier_summary(self, obj):
        tiers = getattr(obj, 'tiers', None)
        if tiers is None:
            return []
        tier_qs = tiers.all() if hasattr(tiers, 'all') else tiers
        if hasattr(tier_qs, 'order_by'):
            iterable = tier_qs.order_by('household_min', 'household_max', 'id')
        else:
            iterable = sorted(
                tier_qs,
                key=lambda t: (t.household_min, t.household_max or 10**9, t.id or 0),
            )
        return [build_tier_summary(tier) for tier in iterable if tier.active]


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
    service_type_label = serializers.CharField(source='get_service_type_display', read_only=True)
    tier_summary = serializers.SerializerMethodField()

    class Meta:
        model = ChefServiceOffering
        fields = [
            'id', 'chef', 'service_type', 'title', 'description', 'active',
            'default_duration_minutes', 'max_travel_miles', 'notes',
            'created_at', 'updated_at', 'tiers', 'service_type_label', 'tier_summary'
        ]
        read_only_fields = ['chef', 'created_at', 'updated_at', 'tiers', 'service_type_label', 'tier_summary']

    def get_tier_summary(self, obj):
        tiers = getattr(obj, 'tiers', None)
        if tiers is None:
            return []
        tier_qs = tiers.all() if hasattr(tiers, 'all') else tiers
        if hasattr(tier_qs, 'order_by'):
            iterable = tier_qs.order_by('household_min', 'household_max', 'id')
        else:
            iterable = sorted(
                tier_qs,
                key=lambda t: (t.household_min, t.household_max or 10**9, t.id or 0),
            )
        return [build_tier_summary(tier) for tier in iterable if tier.active]
