from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import (
    MealPlan, MealPlanMeal, Dish, Ingredient, Order, Cart, MealType, Meal, OrderMeal, 
    ShoppingList, Instruction, MealPlanInstruction, PantryItem, MealPlanMealPantryUsage, SystemUpdate
)
from reviews.models import Review
from django.template.response import TemplateResponse
from django.urls import path
from .email_service import send_system_update_email
from django.contrib import messages
from .tasks import queue_system_update_email

class ReviewInline(GenericTabularInline):
    model = Review
    ct_fk_field = 'object_id'
    ct_field = 'content_type'
    extra = 1
    fields = ('user', 'rating', 'comment', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        # Allow adding reviews inline if needed
        return True

    def has_delete_permission(self, request, obj=None):
        # Allow deletion of reviews inline
        return True

class MealTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'calories', 'fat', 'carbohydrates', 'protein')
    search_fields = ('name', 'chef__user__username')
    list_filter = ('chef',)

class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'featured', 'calories', 'fat', 'carbohydrates', 'protein')
    list_filter = ('chef', 'featured')
    search_fields = ('name', 'chef__user__username', 'ingredients__name')
    filter_horizontal = ('ingredients',)

class OrderMealInline(admin.TabularInline):
    model = OrderMeal
    extra = 1
    readonly_fields = ('meal',)
    fields = ('meal', 'quantity', 'meal_plan_meal')
    # Show meal details inline for reference

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order_date', 'status', 'delivery_method', 'is_paid', 'total_price')
    list_filter = ('status', 'delivery_method', 'is_paid', 'order_date')
    search_fields = ('customer__user__username', 'meal__name')
    inlines = [OrderMealInline]
    readonly_fields = ('order_date', 'updated_at')

class MealAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'start_date', 'price', 'average_rating_display')
    list_filter = ('chef', 'start_date', 'meal_type')
    search_fields = ('name', 'chef__user__username', 'dishes__name', 'dietary_preferences__name', 'custom_dietary_preferences__name')
    filter_horizontal = ('dishes',)
    inlines = [ReviewInline]

    def average_rating_display(self, obj):
        avg = obj.average_rating()
        return f"{avg:.2f}" if avg else "No Ratings"
    average_rating_display.short_description = 'Avg. Rating'

class CartAdmin(admin.ModelAdmin):
    list_display = ('customer', 'get_meals_count')
    search_fields = ('customer__user__username', 'meal__name')

    def get_meals_count(self, obj):
        return obj.meal.count()
    get_meals_count.short_description = 'Meals Count'

class MealPlanMealInline(admin.TabularInline):
    model = MealPlanMeal
    extra = 1
    fields = ('id', 'meal', 'meal_id_display', 'day', 'meal_type')
    readonly_fields = ('id', 'meal_id_display')
    autocomplete_fields = ['meal']

    def meal_id_display(self, obj):
        if obj.meal:
            return obj.meal.id
        return None
    meal_id_display.short_description = 'Meal ID'

class MealPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'week_start_date', 'week_end_date', 'is_approved', 'has_changes', 'get_meals_count', 'average_rating_display')
    list_filter = ('week_start_date', 'week_end_date', 'is_approved', 'has_changes')
    search_fields = ('user__username', 'meal__name')
    inlines = [MealPlanMealInline, ReviewInline]

    def get_meals_count(self, obj):
        return obj.meal.count()
    get_meals_count.short_description = 'Meals Count'

    def average_rating_display(self, obj):
        avg = obj.average_meal_rating()
        return f"{avg:.2f}" if avg else "No Ratings"
    average_rating_display.short_description = 'Avg. Meal Rating'

class MealPlanMealAdmin(admin.ModelAdmin):
    list_display = ('meal_plan', 'meal', 'day', 'meal_type')
    list_filter = ('day', 'meal_type')
    search_fields = ('meal__name', 'meal_plan__user__username')

class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ('meal_plan', 'last_updated')
    search_fields = ('meal_plan__user__username',)

class InstructionAdmin(admin.ModelAdmin):
    list_display = ('meal_plan_meal', 'last_updated')
    search_fields = ('meal_plan_meal__meal__name', 'meal_plan_meal__meal_plan__user__username')

class MealPlanInstructionAdmin(admin.ModelAdmin):
    list_display = ('meal_plan_id', 'meal_plan', 'date', 'is_bulk_prep')

    def meal_plan_id(self, obj):
        return obj.meal_plan.id
    meal_plan_id.short_description = 'Meal Plan ID'

class PantryItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_name', 'quantity', 'used_count', 'expiration_date', 'item_type', 'marked_as_used')
    list_filter = ('item_type', 'marked_as_used', 'expiration_date')
    search_fields = ('user__username', 'item_name')

class MealPlanMealPantryUsageAdmin(admin.ModelAdmin):
    list_display = ('meal_plan_meal', 'pantry_item', 'quantity_used')
    search_fields = ('meal_plan_meal__meal__name', 'pantry_item__item_name')
    list_filter = ('meal_plan_meal__meal__meal_type',)

class SystemUpdateAdmin(admin.ModelAdmin):
    change_list_template = "admin/system_update_form.html"
    list_display = ['subject', 'sent_at', 'sent_by']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send_update/', self.send_update_view, name='send_system_update'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if request.method == 'GET':
            return self.send_update_view(request)
        return super().changelist_view(request, extra_context)

    def send_update_view(self, request):
        print(f"Sending update view with method: {request.method}")
        print(f"POST data: {request.POST if request.method == 'POST' else 'No POST data'}")
        
        if request.method == 'POST':
            subject = request.POST.get('subject')
            message = request.POST.get('message')
            test_mode = request.POST.get('test_mode') == 'on'
            
            print(f"Received form data - Subject: {subject}, Test Mode: {test_mode}")
            
            try:
                # Create SystemUpdate record
                system_update = SystemUpdate.objects.create(
                    subject=subject,
                    message=message,
                    sent_by=request.user
                )
                
                if test_mode:
                    queue_system_update_email.delay(
                        system_update.id,
                        test_mode=True,
                        admin_id=request.user.id
                    )
                    messages.success(request, "Test email has been queued!")
                else:
                    queue_system_update_email.delay(
                        system_update.id,
                        test_mode=False
                    )
                    messages.success(request, "System update email has been queued for all users!")
            except Exception as e:
                print(f"Error in send_update_view: {str(e)}")
                messages.error(request, f"Error queueing email: {str(e)}")
                if 'system_update' in locals():
                    system_update.delete()
                
        return TemplateResponse(request, "admin/system_update_form.html", {})

admin.site.register(MealPlan, MealPlanAdmin)
admin.site.register(Dish, DishAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(MealType, MealTypeAdmin)
admin.site.register(Meal, MealAdmin)
admin.site.register(OrderMeal)  # Show OrderMeal standalone if needed
admin.site.register(MealPlanMeal, MealPlanMealAdmin)
admin.site.register(ShoppingList, ShoppingListAdmin)
admin.site.register(Instruction, InstructionAdmin)
admin.site.register(MealPlanInstruction, MealPlanInstructionAdmin)
admin.site.register(PantryItem, PantryItemAdmin)
admin.site.register(MealPlanMealPantryUsage, MealPlanMealPantryUsageAdmin)
admin.site.register(SystemUpdate, SystemUpdateAdmin)