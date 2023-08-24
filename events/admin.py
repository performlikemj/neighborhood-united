from django.contrib import admin
from .models import Event

class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'location', 'category', 'status')
    list_filter = ('category', 'status', 'date')
    search_fields = ('title', 'description', 'location')
    ordering = ('-date',)
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(Event, EventAdmin)
