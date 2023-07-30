from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import CustomUser, Address
from chefs.models import Chef

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_chef', 'has_requested_chef')
    actions = ['approve_chef_request', 'remove_chef_status']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # This is the case when obj is already created i.e. it's an edit
            return ['is_chef']
        else:
            return []

    def has_requested_chef(self, obj):
        return obj.chef_request is not None
    has_requested_chef.boolean = True
    has_requested_chef.short_description = 'Requested Chef'

    def approve_chef_request(self, request, queryset):
        for user in queryset:
            if user.chef_request and not user.is_chef:
                user.is_chef = True
                user.save()
                Chef.objects.create(
                    user=user,
                    experience=user.chef_request_experience,
                    bio=user.chef_request_bio,
                    profile_pic=user.chef_request_profile_pic,
                )
    approve_chef_request.short_description = "Approve selected chef requests"

    def remove_chef_status(self, request, queryset):
        for user in queryset:
            if user.is_chef:
                user.is_chef = False
                user.current_role = 'customer'
                user.save()
                # Delete the associated Chef instance
                Chef.objects.get(user=user).delete()
    remove_chef_status.short_description = "Remove chef status"

class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_type', 'street', 'city', 'state', 'zipcode', 'country')

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Address, AddressAdmin)