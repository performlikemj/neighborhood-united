# meals/serializers.py
from rest_framework import serializers
from .models import MealPlan, Meal, MealPlanMeal, CustomUser, Order, Ingredient, Dish, PantryItem, Tag, DietaryPreference, ChefMealEvent, ChefMealOrder, ChefMealReview, StripeConnectAccount
from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from django.db.models import Avg



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
    address = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'dietary_preferences', 'allergies', 'custom_allergies', 'custom_dietary_preferences', 'preferred_language', 'address']

    def get_address(self, obj):
        if hasattr(obj, 'address'):
            return {
                'id': obj.address.id,
                'street': obj.address.street,
                'city': obj.address.city,
                'state': obj.address.state,
                'input_postalcode': obj.address.input_postalcode,
                'country': {
                    'code': obj.address.country.code if obj.address.country else None,
                    'name': obj.address.country.name if obj.address.country else None
                }
            }
        return None

class MealSerializer(serializers.ModelSerializer):
    chef_name = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    dietary_preferences = serializers.StringRelatedField(many=True)
    
    class Meta:
        model = Meal
        fields = [
            'id', 'name', 'chef', 'chef_name', 'image', 'description', 
            'price', 'average_rating', 'meal_type', 'dietary_preferences'
        ]
    
    def get_chef_name(self, obj):
        if obj.chef and obj.chef.user:
            return obj.chef.user.get_full_name() or obj.chef.user.username
        return None
    
    def get_average_rating(self, obj):
        return obj.average_rating()

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

class ChefSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Chef
        fields = ['id', 'user', 'user_name', 'bio', 'rating']
        
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

class AddressSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    
    class Meta:
        model = Address
        fields = ['id', 'street_address', 'city', 'state', 'input_postalcode', 'country']

    def get_country(self, obj):
        return {
            'code': obj.country.code if obj.country else None,
            'name': obj.country.name if obj.country else None
        }

class ChefMealEventSerializer(serializers.ModelSerializer):
    chef = ChefSerializer(read_only=True)
    meal = MealSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    
    class Meta:
        model = ChefMealEvent
        fields = [
            'id', 'chef', 'meal', 'event_date', 'event_time', 'order_cutoff_time',
            'max_orders', 'min_orders', 'base_price', 'current_price', 'min_price',
            'orders_count', 'status', 'description', 'special_instructions',
            'created_at', 'updated_at', 'is_available', 'reviews_count', 'average_rating'
        ]
    
    def get_is_available(self, obj):
        return obj.is_available_for_orders()
    
    def get_reviews_count(self, obj):
        return obj.reviews.count()
    
    def get_average_rating(self, obj):
        return obj.reviews.aggregate(Avg('rating'))['rating__avg']

class ChefMealEventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefMealEvent
        fields = [
            'meal', 'event_date', 'event_time', 'order_cutoff_time',
            'max_orders', 'min_orders', 'base_price', 'min_price',
            'status', 'description', 'special_instructions'
        ]
    
    def create(self, validated_data):
        # Set the chef to the current user's chef profile
        user = self.context['request'].user
        try:
            chef = Chef.objects.get(user=user)
        except Chef.DoesNotExist:
            raise serializers.ValidationError("You must be a registered chef to create meal events")
        
        validated_data['chef'] = chef
        validated_data['current_price'] = validated_data['base_price']
        
        return super().create(validated_data)

class ChefMealOrderSerializer(serializers.ModelSerializer):
    meal_event = ChefMealEventSerializer(read_only=True)
    customer = UserSerializer(read_only=True)
    has_review = serializers.SerializerMethodField()
    
    class Meta:
        model = ChefMealOrder
        fields = [
            'id', 'meal_event', 'customer', 'quantity', 'price_paid',
            'status', 'special_requests', 'created_at', 'updated_at',
            'has_review'
        ]
    
    def get_has_review(self, obj):
        return hasattr(obj, 'review')

class ChefMealOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefMealOrder
        fields = ['meal_event', 'quantity', 'special_requests']
    
    def validate_meal_event(self, value):
        if not value.is_available_for_orders():
            raise serializers.ValidationError("This meal event is not available for orders")
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create an Order instance if needed
        from .models import Order
        order = Order.objects.create(
            customer=user,
            address=user.address if hasattr(user, 'address') else None,
            status='Placed'
        )
        
        # Set the customer to the current user
        validated_data['customer'] = user
        validated_data['order'] = order
        validated_data['price_paid'] = validated_data['meal_event'].current_price
        
        return super().create(validated_data)

class ChefMealReviewSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    
    class Meta:
        model = ChefMealReview
        fields = ['id', 'chef_meal_order', 'customer', 'rating', 'comment', 'created_at']
        read_only_fields = ['customer', 'chef', 'meal_event']
    
    def validate_chef_meal_order(self, value):
        # Ensure the order belongs to the current user
        user = self.context['request'].user
        if value.customer != user:
            raise serializers.ValidationError("You can only review your own orders")
        
        # Ensure the order is completed
        if value.status != 'completed':
            raise serializers.ValidationError("You can only review completed orders")
        
        # Ensure the order hasn't been reviewed already
        if hasattr(value, 'review'):
            raise serializers.ValidationError("You have already reviewed this order")
        
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        order = validated_data['chef_meal_order']
        
        # Set additional fields
        validated_data['customer'] = user
        validated_data['chef'] = order.meal_event.chef
        validated_data['meal_event'] = order.meal_event
        
        return super().create(validated_data)

class StripeConnectAccountSerializer(serializers.ModelSerializer):
    chef = ChefSerializer(read_only=True)
    
    class Meta:
        model = StripeConnectAccount
        fields = ['id', 'chef', 'stripe_account_id', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['stripe_account_id', 'is_active', 'created_at', 'updated_at']
