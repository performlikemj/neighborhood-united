from django.contrib import admin
from menus.models import Menu  # Assuming menus is the app where the Menu model resides
from .models import Chef

class MenuInline(admin.TabularInline):  # You can also use admin.StackedInline
    model = Menu
    extra = 1  # How many extra empty rows to display
    # Any other options you want to include

class ChefAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience', 'bio')
    search_fields = ('user__username', 'experience', 'bio')
    list_filter = ('user__is_active',)
    fields = ('user', 'experience', 'bio', 'profile_pic')
    inlines = [MenuInline]  # Add this line


admin.site.register(Chef, ChefAdmin)  # register Chef model with ChefAdmin here