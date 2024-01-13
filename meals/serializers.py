from rest_framework import serializers
from .models import MealPlan, Meal, Order, Cart

class MealPlanSerializer(serializers.ModelSerializer):
    meals = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Meal.objects.all()
    )

    class Meta:
        model = MealPlan
        fields = ['id', 'user', 'meals', 'created_date', 'week_start_date', 'week_end_date', 'order']

class OrderSerializer(serializers.ModelSerializer):
    meals = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Meal.objects.all()
    )
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'customer', 'address', 'meals', 'order_date', 'updated_at', 'status', 'delivery_method', 'special_requests', 'is_paid', 'meal_plan', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()