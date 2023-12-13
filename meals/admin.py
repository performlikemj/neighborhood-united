from django.contrib import admin
from .models import MealPlan, MealPlanMeal, Dish, Ingredient, Order, Cart, MealType, Meal, OrderMeal

class MealTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef')
    search_fields = ('name', 'chef__user__username')

class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef')
    list_filter = ('chef', 'featured')
    search_fields = ('name', 'chef__user__username',)
    filter_horizontal = ('ingredients',)

class OrderMealInline(admin.TabularInline):
    model = OrderMeal
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'order_date', 'status', 'delivery_method', 'is_paid')
    list_filter = ('status', 'delivery_method', 'is_paid', 'order_date')
    search_fields = ('customer__user__username',)
    inlines = [OrderMealInline]

class MealAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'start_date', 'price', 'party_size')
    list_filter = ('chef', 'start_date')
    search_fields = ('name', 'chef__user__username')
    filter_horizontal = ('dishes',)

class CartAdmin(admin.ModelAdmin):
    list_display = ('customer', 'get_meals_count')
    search_fields = ('customer__user__username',)

    def get_meals_count(self, obj):
        return obj.meals.count()
    get_meals_count.short_description = 'Meals Count'

class MealPlanMealInline(admin.TabularInline):
    model = MealPlanMeal
    extra = 1

class MealPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'week_start_date', 'week_end_date', 'get_meals_count')
    list_filter = ('week_start_date', 'week_end_date')
    search_fields = ('user__username',)
    inlines = [MealPlanMealInline]

    def get_meals_count(self, obj):
        return obj.meal.count()
    get_meals_count.short_description = 'Meals Count'

# Register your models here.
admin.site.register(MealPlan, MealPlanAdmin)
admin.site.register(Dish, DishAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(MealType, MealTypeAdmin)
admin.site.register(Meal, MealAdmin)
admin.site.register(OrderMeal)  # For easier management of OrderMeal instances if needed
