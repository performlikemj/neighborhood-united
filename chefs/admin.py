from django.contrib import admin
from meals.models import Meal  
from .models import Chef, ChefRequest, ChefPostalCode, PostalCode


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
    readonly_fields = ('user',)  # Add any fields you want to be read-only
    inlines = [MealInline, ChefPostalCodeInline]

admin.site.register(Chef, ChefAdmin)


class ChefRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved',)
    actions = ['approve_chef_requests']

    def approve_chef_requests(self, request, queryset):
        for chef_request in queryset:
            if not chef_request.is_approved:
                chef_request.is_approved = True
                chef_request.save()
                
                chef, created = Chef.objects.get_or_create(
                    user=chef_request.user,
                    defaults={
                        'experience': chef_request.experience,
                        'bio': chef_request.bio,
                        'profile_pic': chef_request.profile_pic,
                    }
                )
                chef.serving_postalcodes.set(chef_request.requested_postalcodes.all())

    approve_chef_requests.short_description = "Approve selected chef requests"
    filter_horizontal = ('requested_postalcodes',)



admin.site.register(ChefRequest, ChefRequestAdmin)
