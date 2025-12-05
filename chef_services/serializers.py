from decimal import Decimal

from rest_framework import serializers

from custom_auth.models import CustomUser
from .models import (
    ChefServiceOffering,
    ChefServicePriceTier,
    ChefServiceOrder,
    ChefCustomerConnection,
)


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
    target_customer_ids = serializers.PrimaryKeyRelatedField(
        source='target_customers',
        queryset=CustomUser.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = ChefServiceOffering
        fields = [
            'id', 'chef', 'service_type', 'title', 'description', 'active',
            'default_duration_minutes', 'max_travel_miles', 'notes',
            'created_at', 'updated_at', 'tiers', 'service_type_label', 'tier_summary',
            'target_customer_ids',
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

    def _resolve_chef(self):
        chef = self.context.get('chef')
        if chef:
            return chef
        instance = getattr(self, 'instance', None)
        if instance is not None:
            return instance.chef
        return None

    def validate_target_customers(self, customers):
        chef = self._resolve_chef()
        if not chef or not customers:
            return customers

        accepted_ids = set(
            ChefCustomerConnection.objects.filter(
                chef=chef,
                customer__in=customers,
                status=ChefCustomerConnection.STATUS_ACCEPTED,
            ).values_list('customer_id', flat=True)
        )
        invalid = [c.id for c in customers if c.id not in accepted_ids]
        if invalid:
            raise serializers.ValidationError(
                "Target customers must have an accepted connection with the chef. Invalid IDs: %s" % (
                    ", ".join(str(pk) for pk in invalid)
                )
            )
        return customers

    def create(self, validated_data):
        target_customers = validated_data.pop('target_customers', [])
        offering = super().create(validated_data)
        if target_customers:
            offering.target_customers.set(target_customers)
        return offering

    def update(self, instance, validated_data):
        target_customers = validated_data.pop('target_customers', None)
        offering = super().update(instance, validated_data)
        if target_customers is not None:
            offering.target_customers.set(target_customers)
        return offering


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


class ChefCustomerConnectionSerializer(serializers.ModelSerializer):
    chef_id = serializers.IntegerField(read_only=True)
    customer_id = serializers.IntegerField(read_only=True)
    # Include partner names for display purposes
    chef_username = serializers.CharField(source='chef.user.username', read_only=True)
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    customer_first_name = serializers.CharField(source='customer.first_name', read_only=True)
    customer_last_name = serializers.CharField(source='customer.last_name', read_only=True)
    customer_email = serializers.EmailField(source='customer.email', read_only=True)

    class Meta:
        model = ChefCustomerConnection
        fields = [
            'id', 'chef_id', 'customer_id', 'status', 'initiated_by',
            'requested_at', 'responded_at', 'ended_at',
            'chef_username', 'customer_username',
            'customer_first_name', 'customer_last_name', 'customer_email',
        ]
        read_only_fields = fields
