from django.contrib import admin
from .models import Dish, Ingredient, Order, Cart, MealType
from .models import Menu


class MealTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'chef', 'featured', 'get_nutrition_info')
    list_filter = ('chef', 'featured', 'meal_types')  # Add 'meal_types' here
    search_fields = ('name', 'chef__user__username', 'meal_types__name')  # Add 'meal_types__name' here
    filter_horizontal = ('ingredients', 'meal_types')  # Add 'meal_types' here

    def get_nutrition_info(self, obj):
        nutrition_info = obj.get_nutritional_info()
        # Format the nutritional info for display
        return ', '.join(f'{key}: {value}' for key, value in nutrition_info.items())
    get_nutrition_info.short_description = 'Nutritional Information'

class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_email', 'customer_phone', 'order_date', 'total_price')
    list_filter = ('order_date',)
    search_fields = ('customer_name', 'customer_email')

class CartAdmin(admin.ModelAdmin):
    list_display = ('customer', 'get_dishes_count')
    search_fields = ('customer__user__username',)

    def get_dishes_count(self, obj):
        return obj.dishes.count()
    get_dishes_count.short_description = 'Dishes Count'


class MenuAdmin(admin.ModelAdmin):
    list_display = ('chef', 'start_date', 'end_date', 'price')
    list_filter = ('chef', 'start_date', 'end_date', 'price')
    search_fields = ('chef__user__username',)


admin.site.register(Menu, MenuAdmin)
admin.site.register(Dish, DishAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(MealType, MealTypeAdmin)
