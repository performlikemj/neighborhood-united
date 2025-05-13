from django.contrib import admin
from .models import PostalCode, ChefPostalCode

class ChefPostalCodeAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            # This will show the error in the admin message framework
            self.message_user(request, f"Error saving: {str(e)}", level='ERROR')
            raise

admin.site.register(PostalCode)
admin.site.register(ChefPostalCode, ChefPostalCodeAdmin)
