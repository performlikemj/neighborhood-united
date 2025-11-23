from django.contrib import admin

from .models import ServiceOffering, ServiceTier


class ServiceTierInline(admin.TabularInline):
    model = ServiceTier
    extra = 0
    fields = (
        "name",
        "price_cents",
        "billing_cycle",
        "min_commitment_weeks",
        "max_clients",
        "sort_order",
        "is_active",
    )


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "is_deleted", "created_at")
    list_filter = ("category", "is_active", "is_deleted")
    search_fields = ("name", "summary")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ServiceTierInline]


@admin.register(ServiceTier)
class ServiceTierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "offering",
        "price_cents",
        "billing_cycle",
        "sort_order",
        "is_active",
    )
    list_filter = ("billing_cycle", "is_active", "is_deleted")
    search_fields = ("name", "offering__name")
