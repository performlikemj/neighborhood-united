from django.contrib import admin
from .models import Review

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('customer', 'title', 'chef', 'menu')  # Display these fields in the list view
    search_fields = ('customer__username', 'title')  # Allow search by these fields
    readonly_fields = ('customer', 'title', 'text', 'chef', 'menu')  # Make all fields read-only in detail view

    def has_add_permission(self, request):
        return False  # Disallow adding new reviews in admin site

    def has_change_permission(self, request, obj=None):
        return False  # Disallow changing existing reviews in admin site

admin.site.register(Review, ReviewAdmin)
