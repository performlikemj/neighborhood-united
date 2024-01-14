from django.contrib import admin
from .models import CustomUser, Address, UserRole



    
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')



class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'street', 'city', 'state', 'postalcode', 'country')

class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_chef', 'current_role')



admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(UserRole, UserRoleAdmin)
