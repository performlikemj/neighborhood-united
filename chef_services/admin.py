from django.contrib import admin
from .models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder


@admin.register(ChefServiceOffering)
class ChefServiceOfferingAdmin(admin.ModelAdmin):
    list_display = ("id", "chef", "service_type", "title", "active", "updated_at")
    list_filter = ("service_type", "active", "chef")
    search_fields = ("title", "description")


@admin.register(ChefServicePriceTier)
class ChefServicePriceTierAdmin(admin.ModelAdmin):
    list_display = ("id", "offering", "household_min", "household_max", "is_recurring", "currency", "desired_unit_amount_cents", "price_sync_status", "active")
    list_filter = ("is_recurring", "active", "currency", "price_sync_status")
    search_fields = ("display_label", "stripe_price_id")


@admin.register(ChefServiceOrder)
class ChefServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "chef", "offering", "tier", "status", "is_subscription", "created_at")
    list_filter = ("status", "is_subscription", "chef")
    search_fields = ("stripe_session_id", "stripe_subscription_id")
