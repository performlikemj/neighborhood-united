# meals/serializers.py
from rest_framework import serializers
from .models import MealPlan, Meal, MealPlanMeal, CustomUser, Order, Ingredient, Dish, PantryItem
from custom_auth.models import CustomUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'dietary_preferences', 'allergies', 'custom_allergies', 'custom_dietary_preferences', 'preferred_language']


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'calories', 'fat', 'carbohydrates', 'protein']

class DishSerializer(serializers.ModelSerializer):
    ingredients = IngredientSerializer(many=True)

    class Meta:
        model = Dish
        fields = ['id', 'name', 'ingredients', 'calories', 'fat', 'carbohydrates', 'protein']



class MealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meal
        fields = ['id', 'name', 'description', 'dietary_preferences', 'price', 'start_date', 'chef']

class MealPlanMealSerializer(serializers.ModelSerializer):
    meal_plan_meal_id = serializers.IntegerField(source='id', read_only=True)  # Add this line to include the ID
    meal = MealSerializer()
    meal_plan_id = serializers.IntegerField(source='meal_plan.id', read_only=True)
    user = UserSerializer(source='meal_plan.user')  
    class Meta:
        model = MealPlanMeal
        fields = ['meal_plan_meal_id', 'meal_plan_id', 'meal', 'day', 'meal_type', 'user']


class MealPlanSerializer(serializers.ModelSerializer):
    meals = MealPlanMealSerializer(source='mealplanmeal_set', many=True)
    user = UserSerializer()

    class Meta:
        model = MealPlan
        fields = ['id', 'user', 'meals', 'created_date', 'week_start_date', 'week_end_date', 'order', 'is_approved']

class OrderSerializer(serializers.ModelSerializer):
    meals = MealSerializer(many=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'customer', 'address', 'meals', 'order_date', 'updated_at', 'status', 'delivery_method', 'special_requests', 'is_paid', 'meal_plan', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()

class PantryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PantryItem
        fields = ['id', 'item_name', 'quantity', 'expiration_date', 'item_type', 'notes']
        extra_kwargs = {
            'item_name': {'required': True},
            'quantity': {'required': True},
            'item_type': {'required': True},
            'expiration_date': {'required': True},
        }

    # Example of adding validation for quantity
    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    # Optionally override update method if you need custom behavior during updates
    def update(self, instance, validated_data):
        instance.item_name = validated_data.get('item_name', instance.item_name)
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.expiration_date = validated_data.get('expiration_date', instance.expiration_date)
        instance.item_type = validated_data.get('item_type', instance.item_type)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.save()
        return instance
