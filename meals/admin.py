from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import (
    MealPlan, MealPlanMeal, Dish, Ingredient, Order, Cart, MealType, Meal, OrderMeal, 
    ShoppingList, Instruction, MealPlanInstruction, PantryItem, MealPlanMealPantryUsage, SystemUpdate,
    ChefMealEvent, ChefMealOrder, ChefMealReview, StripeConnectAccount, PlatformFeeConfig, PaymentLog
)
from reviews.models import Review
from django.template.response import TemplateResponse
from django.urls import path
from .email_service import send_system_update_email
from django.contrib import messages
from .tasks import queue_system_update_email
from .utils.order_utils import create_chef_meal_orders
from django.utils import timezone
import json
from django.utils.safestring import mark_safe

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

@admin.action(description="Create missing ChefMealOrder records")
def reconcile_chef_meal_orders(modeladmin, request, queryset):
    total_created = 0
    for order in queryset:
        # Only process paid orders
        if not order.is_paid:
            continue
            
        # Use the shared utility function
        created_count = create_chef_meal_orders(order)
        total_created += created_count
    
    modeladmin.message_user(
        request, 
        f"Created {total_created} missing ChefMealOrder records", 
        level=messages.SUCCESS
    )

@admin.action(description="Reconcile payment logs for paid orders")
def reconcile_payment_logs(modeladmin, request, queryset):
    """Ensure that all paid orders have payment logs and confirmed ChefMealOrder records"""
    from decimal import Decimal
    
    payment_logs_created = 0
    chef_orders_updated = 0
    
    for order in queryset:
        if order.is_paid:
            # Update ChefMealOrder records
            chef_meal_orders = order.chef_meal_orders.filter(status='placed')
            for chef_order in chef_meal_orders:
                chef_order.status = 'confirmed'
                chef_order.save()
                chef_orders_updated += 1
                
                # Create PaymentLog if missing
                if not PaymentLog.objects.filter(chef_meal_order=chef_order).exists():
                    PaymentLog.objects.create(
                        chef_meal_order=chef_order,
                        order=order,
                        user=chef_order.customer,
                        chef=chef_order.meal_event.chef,
                        action='charge',
                        amount=float(chef_order.price_paid) * chef_order.quantity,
                        stripe_id=f"reconciled-{order.id}-{chef_order.id}",
                        status='succeeded',
                        details={
                            'reconciled_by_admin': True,
                            'reconciled_at': timezone.now().isoformat(),
                            'admin_user': request.user.username
                        }
                    )
                    payment_logs_created += 1
    
    modeladmin.message_user(
        request, 
        f"Updated {chef_orders_updated} ChefMealOrder records and created {payment_logs_created} missing PaymentLog entries", 
        level=messages.SUCCESS
    )

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order_date', 'status', 'delivery_method', 'is_paid', 'total_price')
    list_filter = ('status', 'is_paid', 'delivery_method', 'order_date')
    search_fields = ('customer__username', 'customer__email', 'id')
    inlines = [OrderMealInline]
    readonly_fields = ('order_date', 'updated_at')
    actions = [reconcile_chef_meal_orders, reconcile_payment_logs]

class MealAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'start_date', 'price', 'average_rating_display', 'has_macro_info', 'has_youtube_videos')
    list_filter = ('chef', 'start_date', 'meal_type')
    search_fields = ('name', 'chef__user__username', 'dishes__name', 'dietary_preferences__name', 'custom_dietary_preferences__name')
    filter_horizontal = ('dishes',)
    inlines = [ReviewInline]
    readonly_fields = ('macro_info_display', 'youtube_videos_display')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'chef', 'creator', 'description', 'meal_type', 'start_date', 'price', 'image')
        }),
        ('Dietary Information', {
            'fields': ('dishes', 'dietary_preferences', 'custom_dietary_preferences')
        }),
        ('Enhanced Information', {
            'fields': ('macro_info_display', 'youtube_videos_display')
        }),
    )

    def average_rating_display(self, obj):
        avg = obj.average_rating()
        return f"{avg:.2f}" if avg else "No Ratings"
    average_rating_display.short_description = 'Avg. Rating'
    
    def has_macro_info(self, obj):
        try:
            return bool(obj.macro_info)
        except (AttributeError, TypeError):
            return False
    has_macro_info.boolean = True
    has_macro_info.short_description = 'Macro Info'
    
    def has_youtube_videos(self, obj):
        try:
            return bool(obj.youtube_videos)
        except (AttributeError, TypeError):
            return False
    has_youtube_videos.boolean = True
    has_youtube_videos.short_description = 'YouTube'
    
    def macro_info_display(self, obj):
        try:
            if not hasattr(obj, 'macro_info') or not obj.macro_info:
                return "No macro information available"
            
            data = json.loads(obj.macro_info)
            html = "<table>"
            html += f"<tr><th>Calories</th><td>{data.get('calories', 'N/A')} kcal</td></tr>"
            html += f"<tr><th>Protein</th><td>{data.get('protein', 'N/A')} g</td></tr>"
            html += f"<tr><th>Carbohydrates</th><td>{data.get('carbohydrates', 'N/A')} g</td></tr>"
            html += f"<tr><th>Fat</th><td>{data.get('fat', 'N/A')} g</td></tr>"
            html += f"<tr><th>Serving Size</th><td>{data.get('serving_size', 'N/A')}</td></tr>"
            html += "</table>"
            return mark_safe(html)
        except Exception as e:
            return f"Error processing macro information: {str(e)}"
    macro_info_display.short_description = 'Macro Information'
    
    def youtube_videos_display(self, obj):
        try:
            if not hasattr(obj, 'youtube_videos') or not obj.youtube_videos:
                return "No YouTube videos available"
            
            data = json.loads(obj.youtube_videos)
            videos = data.get('videos', [])
            if not videos:
                return "No videos found"
            
            html = "<ul>"
            for video in videos:
                title = video.get('title', 'Untitled')
                url = video.get('url', '#')
                channel = video.get('channel', 'Unknown')
                html += f'<li><a href="{url}" target="_blank">{title}</a> ({channel})</li>'
            html += "</ul>"
            return mark_safe(html)
        except Exception as e:
            return f"Error processing YouTube videos: {str(e)}"
    youtube_videos_display.short_description = 'YouTube Videos'

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
    list_display = ('id', 'user', 'week_start_date', 'week_end_date', 'is_approved', 'has_changes', 'get_meals_count')
    list_filter = ('week_start_date', 'week_end_date', 'is_approved', 'has_changes')
    search_fields = ('user__username', 'meal__name')
    inlines = [MealPlanMealInline, ReviewInline]

    def get_meals_count(self, obj):
        return obj.meal.count()
    get_meals_count.short_description = 'Meals Count'

    # def average_rating_display(self, obj):
    #     avg = obj.average_meal_rating()
    #     return f"{avg:.2f}" if avg else "No Ratings"
    # average_rating_display.short_description = 'Avg. Meal Rating'

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

class ChefMealOrderInline(admin.TabularInline):
    model = ChefMealOrder
    extra = 0
    fields = ('customer', 'quantity', 'price_paid', 'status', 'created_at')
    readonly_fields = ('customer', 'price_paid', 'created_at')
    can_delete = False
    show_change_link = True

class ChefMealReviewInline(admin.TabularInline):
    model = ChefMealReview
    extra = 0
    fields = ('customer', 'rating', 'comment', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True
    can_delete = False

class ChefMealEventAdmin(admin.ModelAdmin):
    list_display = ('meal', 'chef', 'event_date', 'event_time', 'status', 'current_price', 'base_price', 'orders_count', 'max_orders')
    list_filter = ('status', 'event_date', 'chef')
    search_fields = ('meal__name', 'chef__user__username', 'description')
    readonly_fields = ('orders_count', 'current_price', 'created_at', 'updated_at')
    inlines = [ChefMealOrderInline]
    date_hierarchy = 'event_date'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add a warning message if this event has orders
        if obj and obj.orders_count > 0:
            help_text = (
                "⚠️ <strong>WARNING:</strong> This event has existing orders! "
                "Changing prices could affect customer charges. "
                "Price increases are blocked through the API but can be changed here. "
                "Make sure you understand the implications before saving."
            )
            form.base_fields['base_price'].help_text = help_text
            form.base_fields['min_price'].help_text = help_text
            
        return form
    
    fieldsets = (
        (None, {
            'fields': ('chef', 'meal', 'status', 'description')
        }),
        ('Scheduling', {
            'fields': ('event_date', 'event_time', 'order_cutoff_time')
        }),
        ('Pricing', {
            'fields': ('base_price', 'current_price', 'min_price')
        }),
        ('Capacity', {
            'fields': ('max_orders', 'min_orders', 'orders_count')
        }),
        ('Additional Information', {
            'fields': ('special_instructions', 'created_at', 'updated_at')
        })
    )

class ChefMealOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'meal_event', 'quantity', 'price_paid', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'meal_event__chef')
    search_fields = ('customer__username', 'meal_event__meal__name', 'meal_event__chef__user__username')
    readonly_fields = ('created_at', 'updated_at', 'stripe_payment_intent_id', 'stripe_refund_id')
    
    fieldsets = (
        (None, {
            'fields': ('order', 'meal_event', 'customer', 'quantity', 'price_paid', 'status')
        }),
        ('Payment Information', {
            'fields': ('stripe_payment_intent_id', 'stripe_refund_id')
        }),
        ('Additional Information', {
            'fields': ('special_requests', 'created_at', 'updated_at')
        })
    )

class ChefMealReviewAdmin(admin.ModelAdmin):
    list_display = ('customer', 'chef', 'meal_event', 'rating', 'created_at')
    list_filter = ('rating', 'created_at', 'chef')
    search_fields = ('customer__username', 'chef__user__username', 'meal_event__meal__name', 'comment')
    readonly_fields = ('created_at',)

class StripeConnectAccountAdmin(admin.ModelAdmin):
    list_display = ('chef', 'stripe_account_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('chef__user__username', 'stripe_account_id')
    readonly_fields = ('created_at', 'updated_at')

class PlatformFeeConfigAdmin(admin.ModelAdmin):
    list_display = ('fee_percentage', 'active', 'created_at')
    list_filter = ('active', 'created_at')
    readonly_fields = ('created_at', 'updated_at')

class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'order', 'chef_meal_order', 'amount', 'status', 'created_at')
    list_filter = ('action', 'status', 'created_at')
    search_fields = ('order__id', 'chef_meal_order__id', 'user__username', 'chef__user__username', 'stripe_id')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('action', 'amount', 'status')
        }),
        ('Related Entities', {
            'fields': ('order', 'chef_meal_order', 'user', 'chef')
        }),
        ('Payment Details', {
            'fields': ('stripe_id', 'details')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )

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
admin.site.register(ChefMealEvent, ChefMealEventAdmin)
admin.site.register(ChefMealOrder, ChefMealOrderAdmin)
admin.site.register(ChefMealReview, ChefMealReviewAdmin)
admin.site.register(StripeConnectAccount, StripeConnectAccountAdmin)
admin.site.register(PlatformFeeConfig, PlatformFeeConfigAdmin)
admin.site.register(PaymentLog, PaymentLogAdmin)