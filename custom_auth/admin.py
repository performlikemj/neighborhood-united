from django.contrib import admin
from .models import CustomUser, Address, UserRole

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    # Removed 'is_chef' and 'has_requested_chef' as they will be handled in the chefs app
    
    # Removed get_readonly_fields function is now redundant since it returns an empty list regardless of whether the object exists or not. Originally, it was used to make the is_chef field read-only in the admin interface.

    # Removed 'approve_chef_request' and 'remove_chef_status' actions as they are moved to chefs app

class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'street', 'city', 'state', 'postalcode', 'country')


class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_chef', 'current_role')


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(UserRole, UserRoleAdmin)

