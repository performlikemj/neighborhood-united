from django.contrib import admin

from .models import Lead, LeadInteraction


class LeadInteractionInline(admin.TabularInline):
    model = LeadInteraction
    extra = 0
    fields = ("interaction_type", "summary", "happened_at", "author", "is_deleted")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "status",
        "source",
        "owner",
        "is_priority",
        "is_deleted",
    )
    list_filter = ("status", "source", "is_priority", "is_deleted")
    search_fields = ("first_name", "last_name", "email", "company")
    inlines = [LeadInteractionInline]


@admin.register(LeadInteraction)
class LeadInteractionAdmin(admin.ModelAdmin):
    list_display = ("lead", "interaction_type", "happened_at", "author", "is_deleted")
    list_filter = ("interaction_type", "is_deleted")
    search_fields = ("lead__first_name", "lead__last_name", "summary")
