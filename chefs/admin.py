from django.contrib import admin
from meals.models import Meal  
from .models import Chef, ChefRequest, ChefPostalCode, PostalCode
from custom_auth.models import UserRole
from django.contrib import messages
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class MealInline(admin.TabularInline):  # You can also use admin.StackedInline
    model = Meal
    extra = 1  # How many extra empty rows to display
    # Any other options you want to include

class ChefPostalCodeInline(admin.TabularInline):
    model = ChefPostalCode
    extra = 1  # Number of extra forms to display

class ChefAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience', 'bio',)
    search_fields = ('user__username', 'experience', 'bio')
    list_filter = ('user__is_active',)
    fields = ('user', 'experience', 'bio', 'profile_pic', 'chef_embedding')
    inlines = [MealInline, ChefPostalCodeInline]
    
    def save_model(self, request, obj, form, change):
        """
        Update UserRole when Chef is created or saved
        """
        try:
            super().save_model(request, obj, form, change)
            # Update or create UserRole for this user
            user_role, created = UserRole.objects.get_or_create(user=obj.user)
            user_role.is_chef = True
            user_role.current_role = 'chef'
            user_role.save()
        except Exception as e:
            self.message_user(request, f"Error saving: {str(e)}", level='ERROR')
            # Log the error for debugging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving Chef: {str(e)}")
            raise

admin.site.register(Chef, ChefAdmin)


class ChefRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved',)
    actions = ['approve_chef_requests']
    
    def save_model(self, request, obj, form, change):
        """
        Handle individual approval when admin checks is_approved checkbox
        """
        was_approved_before = False
        if change:  # If this is an update, not a new record
            try:
                original_obj = ChefRequest.objects.get(pk=obj.pk)
                was_approved_before = original_obj.is_approved
            except ChefRequest.DoesNotExist:
                pass
        
        # Save the ChefRequest first
        super().save_model(request, obj, form, change)
        
        # If the request was just approved (not already approved before)
        if obj.is_approved and not was_approved_before:
            try:
                with transaction.atomic():
                    # Try to get existing Chef or create a new one
                    chef, created = Chef.objects.get_or_create(
                        user=obj.user
                    )
                    
                    # Always update the Chef with data from ChefRequest
                    if obj.experience:
                        chef.experience = obj.experience
                    if obj.bio:
                        chef.bio = obj.bio
                    if obj.profile_pic:
                        chef.profile_pic = obj.profile_pic
                    
                    # Save the chef object
                    chef.save()
                    
                    # Set postal codes if there are any
                    if obj.requested_postalcodes.exists():
                        chef.serving_postalcodes.set(obj.requested_postalcodes.all())
                    
                    # Update UserRole for this user
                    user_role, created = UserRole.objects.get_or_create(user=obj.user)
                    user_role.is_chef = True
                    user_role.current_role = 'chef'
                    user_role.save()
                    
                    messages.success(request, f"Successfully approved chef request for {obj.user.username}.")
                    
            except Exception as e:
                messages.error(request, f"Error approving request for {obj.user.username}: {str(e)}")
                logger.error(f"Error in save_model for ChefRequest {obj.pk}: {str(e)}")


    def approve_chef_requests(self, request, queryset):
        success_count = 0
        error_count = 0
        
        for chef_request in queryset:
            try:
                with transaction.atomic():
                    if not chef_request.is_approved:
                        # Mark the request as approved
                        chef_request.is_approved = True
                        chef_request.save()
                        
                        # Try to get existing Chef or create a new one
                        chef, created = Chef.objects.get_or_create(
                            user=chef_request.user
                        )
                        
                        # Always update the Chef with data from ChefRequest
                        if chef_request.experience:
                            chef.experience = chef_request.experience
                        if chef_request.bio:
                            chef.bio = chef_request.bio
                        if chef_request.profile_pic:
                            chef.profile_pic = chef_request.profile_pic
                        
                        # Save the chef object
                        chef.save()
                        
                        # Set postal codes if there are any
                        if chef_request.requested_postalcodes.exists():
                            chef.serving_postalcodes.set(chef_request.requested_postalcodes.all())
                        
                        # Update UserRole for this user
                        user_role, created = UserRole.objects.get_or_create(user=chef_request.user)
                        user_role.is_chef = True
                        user_role.current_role = 'chef'
                        user_role.save()
                        
                        success_count += 1
            except Exception as e:
                error_count += 1
                messages.error(request, f"Error approving request for {chef_request.user.username}: {str(e)}")
        
        if success_count > 0:
            messages.success(request, f"Successfully approved {success_count} chef request(s).")
        if error_count > 0:
            messages.warning(request, f"Failed to approve {error_count} chef request(s).")

    approve_chef_requests.short_description = "Approve selected chef requests"
    filter_horizontal = ('requested_postalcodes',)



admin.site.register(ChefRequest, ChefRequestAdmin)
