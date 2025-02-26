# meals/serializers.py
from rest_framework import serializers
from .models import MealPlan, Meal, MealPlanMeal, CustomUser, Order, Ingredient, Dish, PantryItem, Tag, DietaryPreference
from custom_auth.models import CustomUser



class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'calories', 'fat', 'carbohydrates', 'protein']

class DishSerializer(serializers.ModelSerializer):
    ingredients = IngredientSerializer(many=True)

    class Meta:
        model = Dish
        fields = ['id', 'name', 'ingredients', 'calories', 'fat', 'carbohydrates', 'protein']



class DietaryPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietaryPreference
        fields = ['id', 'name']

class UserSerializer(serializers.ModelSerializer):
    dietary_preferences = DietaryPreferenceSerializer(many=True, read_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'dietary_preferences', 'allergies', 'custom_allergies', 'custom_dietary_preferences', 'preferred_language']


class MealSerializer(serializers.ModelSerializer):
    dietary_preferences = DietaryPreferenceSerializer(many=True, read_only=True)
    
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
        fields = ['id', 'user', 'meals', 'created_date', 'week_start_date', 'week_end_date', 'order', 'is_approved', 'meal_prep_preference']

class OrderSerializer(serializers.ModelSerializer):
    meals = MealSerializer(many=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'customer', 'address', 'meals', 'order_date', 'updated_at', 'status', 'delivery_method', 'special_requests', 'is_paid', 'meal_plan', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()

class PantryItemSerializer(serializers.ModelSerializer):
    tags = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=Tag.objects.all(),
        required=False
    )
    class Meta:
        model = PantryItem
        fields = ['id', 'item_name', 'quantity', 'expiration_date', 'item_type', 'notes', 'tags', 'weight_per_unit', 'weight_unit']
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

    def validate_weight_per_unit(self, value):
        """
        Example validation if you want to ensure weight_per_unit >= 0.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Weight per unit cannot be negative.")
        return value

    def update(self, instance, validated_data):
        # Only update fields that appear in validated_data
        instance.item_name = validated_data.get('item_name', instance.item_name)
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.used_count = validated_data.get('used_count', instance.used_count)
        instance.expiration_date = validated_data.get('expiration_date', instance.expiration_date)
        instance.item_type = validated_data.get('item_type', instance.item_type)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.weight_per_unit = validated_data.get('weight_per_unit', instance.weight_per_unit)
        instance.weight_unit = validated_data.get('weight_unit', instance.weight_unit)
        
        # handle tags if needed
        if 'tags' in validated_data:
            tags = validated_data['tags']
            instance.tags.set(tags)
        
        instance.save()
        return instance
