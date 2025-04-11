# meals/serializers.py
from rest_framework import serializers
from .models import MealPlan, Meal, MealPlanMeal, CustomUser, Order, Ingredient, Dish, PantryItem, Tag, DietaryPreference, ChefMealEvent, ChefMealOrder, ChefMealReview, StripeConnectAccount, OrderMeal
from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from django.db.models import Avg
from django.utils import timezone
from django.db.models import F
from django.db.models import Q
import decimal
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


# --- Define Simple Serializers First to Break Circular Dependencies ---

# Simple serializer for use within ChefMealEventSerializer
class SimpleChefMealOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_id = serializers.IntegerField(source='customer.id', read_only=True)

    class Meta:
        model = ChefMealOrder
        fields = ['id', 'customer_id', 'customer_name', 'quantity', 'status', 'special_requests', 'created_at']

# Simple serializer for use within ChefMealOrderSerializer
class SimpleChefMealEventSerializer(serializers.ModelSerializer):
    # Assuming ChefSerializer and MealSerializer are defined above
    chef_name = serializers.CharField(source='chef.user.get_full_name', read_only=True)
    meal_name = serializers.CharField(source='meal.name', read_only=True)
    meal_id = serializers.IntegerField(source='meal.id', read_only=True)
    chef_id = serializers.IntegerField(source='chef.id', read_only=True)

    class Meta:
        model = ChefMealEvent
        fields = ['id', 'meal_id', 'meal_name', 'chef_id', 'chef_name', 'event_date', 'event_time']


# --- Original Serializer Definitions (Modified) ---

class IngredientSerializer(serializers.ModelSerializer):
    chef_name = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = [
            'id', 'name', 'chef', 'chef_name', 'calories', 
            'fat', 'carbohydrates', 'protein'
        ]
        read_only_fields = ['chef', 'chef_name']
    
    def get_chef_name(self, obj):
        if obj.chef and obj.chef.user:
            return obj.chef.user.username
        return None

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
                'display_postalcode': obj.address.display_postalcode or obj.address.input_postalcode,
                'country': {
                    'code': obj.address.country.code if obj.address.country else None,
                    'name': obj.address.country.name if obj.address.country else None
                }
            }
        return None

class ChefSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Chef
        fields = ['id', 'user', 'user_name', 'bio']
        
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

class MealSerializer(serializers.ModelSerializer):
    chef_name = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    dietary_preferences = serializers.StringRelatedField(many=True)
    is_chef_meal = serializers.SerializerMethodField()
    chef_meal_events = serializers.SerializerMethodField()
    is_compatible = serializers.SerializerMethodField()
    
    class Meta:
        model = Meal
        fields = [
            'id', 'name', 'chef', 'chef_name', 'image', 'description', 
            'price', 'average_rating', 'meal_type', 'dietary_preferences',
            'is_chef_meal', 'chef_meal_events', 'is_compatible'
        ]
    
    def get_chef_name(self, obj):
        if obj.chef and obj.chef.user:
            return obj.chef.user.get_full_name() or obj.chef.user.username
        return None
    
    def get_average_rating(self, obj):
        return obj.average_rating()
    
    def get_is_chef_meal(self, obj):
        """Indicate if this is a meal created by a chef."""
        return obj.chef is not None
    
    def get_is_compatible(self, obj):
        """
        Check if this meal is compatible with the user's dietary preferences
        using the application's existing compatibility checking system.
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return True  # Default to compatible for unauthenticated users
            
        user = request.user
        
        # Check if user has "Everything" preference (meaning no restrictions)
        if user.dietary_preferences.filter(name='Everything').exists() and user.dietary_preferences.count() == 1:
            return True
        
        # Use existing compatibility caching system
        from .models import MealCompatibility
        
        # Check compatibility for each of the user's dietary preferences
        user_preferences = user.dietary_preferences.exclude(name='Everything').values_list('name', flat=True)
        
        if not user_preferences:
            return True  # No specific dietary preferences, so all meals are compatible
        
        # Check if we have cached compatibility results for all preferences
        for pref_name in user_preferences:
            cached_analysis = MealCompatibility.objects.filter(
                meal=obj,
                preference_name=pref_name
            ).first()
            
            # If we have a cached result showing incompatibility or low confidence, return False
            if cached_analysis and (not cached_analysis.is_compatible or cached_analysis.confidence < 0.7):
                return False
                
            # If we don't have a cached result, we'd need to call analyze_meal_compatibility
            # But since that's an expensive operation for a serializer, we'll defer to the
            # existing system to handle that and just return a default of True
            if not cached_analysis:
                # Check if at least one of the meal's dietary tags matches the user preference
                if obj.dietary_preferences.filter(name=pref_name).exists():
                    return True
                # If uncertain, return True by default - the full compatibility check
                # can be done in a more appropriate context than a serializer
                return True
                
        # If we've checked all preferences and none returned False, the meal is compatible
        return True
    
    def get_chef_meal_events(self, obj):
        """Return upcoming chef meal events for this meal, if any."""
        # Only include this data if it's a chef meal
        if not obj.chef:
            return []
            
        # Get upcoming events for this meal that are still available
        now = timezone.now()
        events = obj.events.filter(
            event_date__gte=now.date(),
            status__in=['scheduled', 'open'],
            order_cutoff_time__gt=now,
            orders_count__lt=F('max_orders')
        ).order_by('event_date', 'event_time')[:5]  # Limit to 5 upcoming events
        
        # Format the events data
        event_data = []
        for event in events:
            event_data.append({
                'id': event.id,
                'event_date': event.event_date,
                'event_time': str(event.event_time),
                'order_cutoff_time': event.order_cutoff_time,
                'current_price': float(event.current_price),
                'orders_count': event.orders_count,
                'max_orders': event.max_orders,
                'status': event.status
            })
            
        return event_data

class MealPlanMealSerializer(serializers.ModelSerializer):
    meal_plan_meal_id = serializers.IntegerField(source='id', read_only=True)  # Add this line to include the ID
    meal = MealSerializer()
    meal_plan_id = serializers.IntegerField(source='meal_plan.id', read_only=True)
    user = UserSerializer(source='meal_plan.user')
    is_chef_meal = serializers.SerializerMethodField()
    chef_name = serializers.SerializerMethodField()
    chef_meal_event = serializers.SerializerMethodField()
    chef_meal_order = serializers.SerializerMethodField()
    
    class Meta:
        model = MealPlanMeal
        fields = [
            'meal_plan_meal_id', 'meal_plan_id', 'meal', 'day', 'meal_type', 'user',
            'is_chef_meal', 'chef_name', 'chef_meal_event', 'chef_meal_order'
        ]
    
    def get_is_chef_meal(self, obj):
        """Determine if this meal was created by a chef."""
        return obj.meal.chef is not None
    
    def get_chef_name(self, obj):
        """Get the chef's name if this is a chef meal."""
        if obj.meal.chef and obj.meal.chef.user:
            return obj.meal.chef.user.get_full_name() or obj.meal.chef.user.username
        return None
    
    def get_chef_meal_event(self, obj):
        """Get the most relevant chef meal event for this meal."""
        from django.utils import timezone
        from django.db.models import F
        
        # Only look for events if this is a chef meal
        if not obj.meal.chef:
            return None
            
        # Find the most relevant upcoming event for this meal
        now = timezone.now()
        event = obj.meal.events.filter(
            event_date__gte=now.date(),
            status__in=['scheduled', 'open'],
            order_cutoff_time__gt=now,
            orders_count__lt=F('max_orders')
        ).order_by('event_date', 'event_time').first()
        
        if not event:
            return None
            
        return {
            'id': event.id,
            'event_date': event.event_date,
            'event_time': str(event.event_time),
            'order_cutoff_time': event.order_cutoff_time,
            'current_price': float(event.current_price),
            'orders_count': event.orders_count,
            'max_orders': event.max_orders,
            'status': event.status
        }
    
    def get_chef_meal_order(self, obj):
        """Get the associated chef meal order if any exists."""
        from django.utils import timezone
        request = self.context.get('request')
        
        # Only try to find orders if this is a chef meal and we have a user
        if not obj.meal.chef or not request or not request.user.is_authenticated:
            return None
        
        # Find the associated chef meal order for this user/meal
        # Import the ChefMealOrder model
        from .models import ChefMealOrder
        
        # Get any active orders placed by this user for this meal
        order = ChefMealOrder.objects.filter(
            customer=request.user,
            meal_event__meal=obj.meal,
            status__in=['placed', 'confirmed']
        ).order_by('-created_at').first()
        
        if not order:
            return None
            
        return {
            'id': order.id,
            'status': order.status,
            'event_id': order.meal_event.id,
            'created_at': order.created_at
        }

class MealPlanSerializer(serializers.ModelSerializer):
    meals = MealPlanMealSerializer(source='mealplanmeal_set', many=True)
    user = UserSerializer()
    payment_required = serializers.SerializerMethodField()
    pending_order_id = serializers.SerializerMethodField()
    payment_details = serializers.SerializerMethodField()

    class Meta:
        model = MealPlan
        fields = ['id', 'user', 'meals', 'created_date', 'week_start_date', 'week_end_date', 'order', 'is_approved', 'meal_prep_preference', 'payment_required', 'pending_order_id', 'payment_details']

    def get_payment_required(self, obj):
        """Check if the meal plan has an associated order that is unpaid."""
        logger.debug(f"[DEBUG] Checking payment_required for MealPlan {obj.id}")
        logger.debug(f"[DEBUG] MealPlan.order: {obj.order}")
        
        if obj.order and not obj.order.is_paid:
            # Further check if the order actually has items requiring payment
            order_total = obj.order.total_price()
            logger.debug(f"[DEBUG] Order #{obj.order.id} total_price: {order_total}")
            
            # Log details about order meals
            order_meals = obj.order.ordermeal_set.all()
            logger.debug(f"[DEBUG] Order has {order_meals.count()} meal items")
            
            for om in order_meals:
                event_price = None
                if hasattr(om, 'chef_meal_event') and om.chef_meal_event:
                    event_price = om.chef_meal_event.current_price
                
                logger.debug(f"[DEBUG] OrderMeal #{om.id}: Meal '{om.meal.name}', " 
                             f"chef_meal_event: {om.chef_meal_event.id if om.chef_meal_event else None}, "
                             f"event_price: {event_price}, quantity: {om.quantity}")
            
            return order_total is not None and order_total > 0
        return False

    def get_pending_order_id(self, obj):
        """Return the ID of the associated order if payment is required."""
        if obj.order and not obj.order.is_paid:
             order_total = obj.order.total_price()
             if order_total is not None and order_total > 0:
                return obj.order.id
        return None
        
    def get_payment_details(self, obj):
        """Provide detailed payment information for this meal plan."""
        if not obj.order:
            return {
                "status": "no_order",
                "message": "No order has been created for this meal plan."
            }
            
        order = obj.order
        total_price = order.total_price()
        
        if order.is_paid:
            return {
                "status": "paid",
                "message": "This meal plan has been paid for.",
                "payment_date": order.updated_at,
                "total_paid": float(total_price)
            }
            
        if total_price is None or total_price <= 0:
            return {
                "status": "no_payment_needed",
                "message": "No payment is required for this meal plan."
            }
            
        # Get detailed breakdown of the order items
        breakdown = []
        chef_meal_count = 0
        
        for order_meal in order.ordermeal_set.select_related('meal', 'chef_meal_event', 'meal_plan_meal').all():
            # Skip already paid meals
            if hasattr(order_meal.meal_plan_meal, 'already_paid') and order_meal.meal_plan_meal.already_paid:
                continue
                
            is_chef_meal = order_meal.chef_meal_event is not None
            if is_chef_meal:
                chef_meal_count += 1
                
            # Get pricing
            unit_price = order_meal.get_price()
            subtotal = unit_price * order_meal.quantity
                
            breakdown.append({
                "meal_id": order_meal.meal.id,
                "meal_name": order_meal.meal.name,
                "unit_price": float(unit_price),
                "quantity": order_meal.quantity,
                "subtotal": float(subtotal),
                "is_chef_meal": is_chef_meal
            })
            
        return {
            "status": "payment_required",
            "message": "Payment is required for this meal plan.",
            "order_id": order.id,
            "total_price": float(total_price),
            "chef_meal_count": chef_meal_count,
            "breakdown": breakdown
        }

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
            'expiration_date': {'required': False},
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

class AddressSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    
    class Meta:
        model = Address
        fields = ['id', 'street', 'city', 'state', 'input_postalcode', 'country']
        # display_postalcode is handled internally and not exposed to the API

    def get_country(self, obj):
        return {
            'code': obj.country.code if obj.country else None,
            'name': obj.country.name if obj.country else None
        }
    
    def to_representation(self, instance):
        """
        Use the display_postalcode for showing to users if it exists, otherwise use input_postalcode
        """
        representation = super().to_representation(instance)
        # If we have a display version, use it for the API response
        if instance.display_postalcode:
            representation['input_postalcode'] = instance.display_postalcode
        return representation
        
    def create(self, validated_data):
        # Store the original input as display format before normalizing
        if 'input_postalcode' in validated_data and validated_data['input_postalcode']:
            # Save the display version
            original_postal_code = validated_data['input_postalcode']
            validated_data['display_postalcode'] = original_postal_code
            
            # Normalize the input_postalcode for storage
            if 'country' in validated_data and validated_data['country']:
                import re
                validated_data['input_postalcode'] = re.sub(
                    r'[^A-Z0-9]', '', 
                    validated_data['input_postalcode'].upper()
                )
                
        return super().create(validated_data)
        
    def update(self, instance, validated_data):
        # If postal code is being updated, save the display version
        if 'input_postalcode' in validated_data and validated_data['input_postalcode']:
            # Store new display format
            original_postal_code = validated_data['input_postalcode']
            validated_data['display_postalcode'] = original_postal_code
            
            # Normalize the input_postalcode
            if 'country' in validated_data and validated_data['country'] or instance.country:
                country = validated_data.get('country', instance.country)
                import re
                validated_data['input_postalcode'] = re.sub(
                    r'[^A-Z0-9]', '', 
                    validated_data['input_postalcode'].upper()
                )
                
        return super().update(instance, validated_data)

# Full ChefMealEventSerializer now uses SimpleChefMealOrderSerializer for nesting
class ChefMealEventSerializer(serializers.ModelSerializer):
    chef = ChefSerializer(read_only=True)
    meal = MealSerializer(read_only=True)
    is_available = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    # Use the simple serializer here to break the cycle
    active_orders = SimpleChefMealOrderSerializer(many=True, read_only=True, source='orders') # Use source='orders' if that's the related name
    chef_earnings = serializers.SerializerMethodField()
    fulfillment_stats = serializers.SerializerMethodField()
    # user_order might also need simplification if it uses the full ChefMealOrderSerializer
    user_order = serializers.SerializerMethodField() # Check implementation of get_user_order
    pricing_details = serializers.SerializerMethodField()

    class Meta:
        model = ChefMealEvent
        fields = [
            'id', 'chef', 'meal', 'event_date', 'event_time', 'order_cutoff_time',
            'max_orders', 'min_orders', 'base_price', 'current_price', 'min_price',
            'orders_count', 'status', 'description', 'special_instructions',
            'created_at', 'updated_at', 'is_available', 'reviews_count', 'average_rating',
            'active_orders', 'chef_earnings', 'fulfillment_stats', 'user_order', 'pricing_details'
        ]

    def get_is_available(self, obj):
        return obj.is_available_for_orders()
    
    def get_reviews_count(self, obj):
        return obj.reviews.count()
    
    def get_average_rating(self, obj):
        return obj.reviews.aggregate(Avg('rating'))['rating__avg']
    
    def get_pricing_details(self, obj):
        """
        Provide detailed information about how pricing works for this event,
        including the current price, how it's calculated, and future price points.
        """
        # Calculate price values at different order quantities
        price_range = float(obj.base_price) - float(obj.min_price)
        discount_per_order = price_range * 0.05  # 5% of the range per order
        
        # Build price points for different quantities
        price_points = []
        current_orders = obj.orders_count
        
        # Calculate prices at various order points
        for order_count in range(1, obj.max_orders + 1):
            # For each order after the first one, reduce price
            if order_count <= 1:
                price = float(obj.base_price)
            else:
                total_discount = discount_per_order * (order_count - 1)
                price = max(float(obj.base_price) - total_discount, float(obj.min_price))
            
            price_points.append({
                "orders": order_count,
                "price": round(price, 2),
                "is_current": order_count == current_orders
            })
        
        # Create a simple explanation of the pricing model
        if current_orders <= 1:
            current_explanation = "This is the starting price."
        else:
            discount_amount = round(float(obj.base_price) - float(obj.current_price), 2)
            discount_percent = round((discount_amount / float(obj.base_price)) * 100, 1)
            current_explanation = f"Group discount: ${discount_amount} off (saves {discount_percent}%) with {current_orders} orders."
        
        # Calculate possible future savings
        future_price = max(float(obj.base_price) - (discount_per_order * obj.max_orders), float(obj.min_price))
        max_savings = round(float(obj.base_price) - future_price, 2)
        max_discount_percent = round((max_savings / float(obj.base_price)) * 100, 1)
        
        return {
            "base_price": float(obj.base_price),
            "current_price": float(obj.current_price),
            "min_price": float(obj.min_price),
            "orders_count": obj.orders_count,
            "current_explanation": current_explanation,
            "max_possible_savings": max_savings,
            "max_discount_percent": max_discount_percent,
            "price_points": price_points,
            "pricing_formula": "For each order after the first, the price decreases by 5% of the difference between base price and minimum price."
        }
    
    def get_user_order(self, obj):
        """Get the current user's order for this event if it exists."""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        order = obj.orders.filter(
            customer=request.user,
            status__in=['placed', 'confirmed']
        ).order_by('-created_at').first()

        if not order:
            return None

        # IMPORTANT: Use the SIMPLE serializer here too if the full one causes recursion
        serializer = SimpleChefMealOrderSerializer(order, context=self.context)
        # Original line (potentially recursive): serializer = ChefMealOrderSerializer(order, context=self.context)
        return serializer.data
    
    def get_active_orders(self, obj):
        # get_active_orders method is likely no longer needed if using source='orders' above
        # def get_active_orders(self, obj):
        #     active_orders = obj.orders.filter(
        #         status__in=['placed', 'confirmed']
        #     ).select_related('customer', 'order').order_by('created_at')
        #     serializer = SimpleChefMealOrderSerializer(active_orders, many=True, context=self.context)
        #     return serializer.data
        pass

    def get_chef_earnings(self, obj):
        """Calculate the chef's expected earnings for this event after platform fees"""
        from .models import PlatformFeeConfig
        from decimal import Decimal
        
        # Get all confirmed/placed orders
        active_orders = obj.orders.filter(status__in=['placed', 'confirmed'])
        
        # Calculate total revenue
        total_revenue = sum(order.price_paid * order.quantity for order in active_orders)
        
        # Get platform fee percentage
        platform_fee_pct = PlatformFeeConfig.get_active_fee()
        
        # Calculate platform fee amount
        platform_fee = (total_revenue * Decimal(platform_fee_pct) / Decimal(100)).quantize(Decimal('0.01'))
        
        # Calculate chef earnings
        chef_earnings = total_revenue - platform_fee
        
        return {
            'total_revenue': float(total_revenue),
            'platform_fee_percentage': float(platform_fee_pct),
            'platform_fee_amount': float(platform_fee),
            'chef_earnings': float(chef_earnings)
        }
    
    def get_fulfillment_stats(self, obj):
        """Provide statistics about order fulfillment status"""
        from django.db.models import Count
        
        # Get counts of orders by status
        status_counts = obj.orders.values('status').annotate(count=Count('status'))
        
        # Create a dictionary with all possible statuses initialized to zero
        stats = {status: 0 for status, _ in obj.orders.model.STATUS_CHOICES}
        
        # Update with actual counts
        for item in status_counts:
            stats[item['status']] = item['count']
        
        # Add total active orders
        active_orders = stats.get('placed', 0) + stats.get('confirmed', 0)
        
        return {
            'status_counts': stats,
            'active_orders': active_orders,
            'completed_orders': stats.get('completed', 0),
            'cancelled_orders': stats.get('cancelled', 0) + stats.get('refunded', 0),
        }

# Full ChefMealOrderSerializer now uses SimpleChefMealEventSerializer for nesting
class ChefMealOrderSerializer(serializers.ModelSerializer):
    # Use the simple serializer here to break the cycle
    meal_event_details = SimpleChefMealEventSerializer(source='meal_event', read_only=True)
    customer_details = UserSerializer(source='customer', read_only=True)
    meal_name = serializers.CharField(source='meal_event.meal.name', read_only=True)
    total_price = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()

    class Meta:
        model = ChefMealOrder
        fields = [
            'id', 'order', 'meal_event', 'meal_event_details', 'customer', 'customer_details',
            'meal_plan_meal',
            'quantity', 'price_paid', 'status', 'created_at', 'updated_at',
            'stripe_payment_intent_id', 'stripe_refund_id', 'price_adjustment_processed',
            'special_requests',
            'meal_name', 'total_price', 'unit_price'
        ]
        read_only_fields = [
            'customer', 'status', 'price_paid', 'created_at', 'updated_at',
            'stripe_payment_intent_id', 'stripe_refund_id', 'price_adjustment_processed'
        ]

    def get_total_price(self, obj):
        """Calculates the total price based on price_paid (per unit) and quantity."""
        # Price_paid is intended to be the *total* price paid for the quantity
        # If price_paid is None, try calculating from the event's current price
        if obj.price_paid is not None:
            total = Decimal(obj.price_paid) # Assuming price_paid is already total
        elif obj.meal_event and obj.meal_event.current_price is not None:
             # Fallback: calculate from current event price
             unit_price = Decimal(obj.meal_event.current_price)
             total = unit_price * obj.quantity
        else:
             total = Decimal('0.00') # Default if no price info available
             
        # --- Print in get_total_price (ChefMealOrderSerializer) ---
        print(f"[DEBUG] ChefMealOrderSerializer: get_total_price for CMO id={obj.id}")
        print(f"[DEBUG]   - Quantity: {obj.quantity}")
        print(f"[DEBUG]   - Stored Price Paid: {obj.price_paid}")
        print(f"[DEBUG]   - Event Current Price: {obj.meal_event.current_price if obj.meal_event else 'N/A'}")
        print(f"[DEBUG]   - Calculated/Used Total: {total}")
        # --- End Print ---
             
        return str(total.quantize(Decimal('0.01')))

    def get_unit_price(self, obj):
        """Calculates the unit price."""
        if obj.quantity > 0 and obj.price_paid is not None:
            # If price_paid is the total, calculate unit price
            unit_price = Decimal(obj.price_paid) / obj.quantity
        elif obj.meal_event and obj.meal_event.current_price is not None:
             # Fallback: use the event's current price as unit price
             unit_price = Decimal(obj.meal_event.current_price)
        else:
             unit_price = Decimal('0.00')
             
        # --- Print in get_unit_price (ChefMealOrderSerializer) ---
        print(f"[DEBUG] ChefMealOrderSerializer: get_unit_price for CMO id={obj.id}. Unit Price: {unit_price}")
        # --- End Print ---

        return str(unit_price.quantize(Decimal('0.01')))

    def to_representation(self, instance):
        print(f"[DEBUG] ChefMealOrderSerializer: Starting to_representation for CMO id={instance.id}") # Added print
        data = super().to_representation(instance)
        # --- Print final values in to_representation (ChefMealOrderSerializer) ---
        print(f"[DEBUG] ChefMealOrderSerializer: Representation for CMO id={instance.id}: quantity={data.get('quantity')}, price_paid={data.get('price_paid')}, unit_price={data.get('unit_price')}, total_price={data.get('total_price')}")
        # --- End Print ---
        return data

# This serializer uses ChefMealOrderSerializer, which should now be safe
class OrderWithChefMealsSerializer(serializers.ModelSerializer):
    customer_details = UserSerializer(source='customer', read_only=True)
    chef_meal_orders = ChefMealOrderSerializer(many=True, read_only=True)
    price_breakdown = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'customer_details', 'order_date', 'updated_at', 'status',
            'delivery_method', 'special_requests', 'is_paid',
            'chef_meal_orders', 'total_price', 'price_breakdown'
        ]

    def get_price_breakdown(self, obj):
        print(f"[DEBUG] OrderSerializer: Running get_price_breakdown for Order id={obj.id}") # Added print
        breakdown = []
        # Ensure related OrderMeals are fetched efficiently
        order_meals = obj.ordermeal_set.select_related('meal', 'chef_meal_event', 'meal_plan_meal').all() # Added meal_plan_meal
        
        calculated_total = Decimal('0.00') # Keep track of calculated total here

        for order_meal in order_meals:
            # Use the OrderMeal's method to get the correct price
            unit_price = order_meal.get_price() 
            quantity = order_meal.quantity
            
            # Ensure quantity is at least 1
            if quantity is None or quantity < 1:
                 quantity = 1
            
            # Ensure unit_price is a Decimal
            if not isinstance(unit_price, Decimal):
                unit_price = Decimal(str(unit_price)) # Convert safely
                
            subtotal = unit_price * quantity
            calculated_total += subtotal
            
            # --- Print inside price_breakdown loop ---
            print(f"[DEBUG] OrderSerializer: Processing OrderMeal id={order_meal.id} for Order id={obj.id}")
            print(f"[DEBUG]   - Meal Name: {order_meal.meal.name}")
            print(f"[DEBUG]   - Unit Price: {unit_price}")
            print(f"[DEBUG]   - Quantity: {quantity}") # <-- Check this quantity
            print(f"[DEBUG]   - Calculated Subtotal: {subtotal}")
            # --- End Print ---

            breakdown.append({
                'meal_id': order_meal.meal.id,
                'meal_name': order_meal.meal.name,
                'quantity': quantity,
                'unit_price': float(unit_price), # Convert final value to float for JSON
                'subtotal': float(subtotal), # Convert final value to float for JSON
                'is_chef_meal': order_meal.chef_meal_event is not None,
                'chef_meal_event_id': order_meal.chef_meal_event.id if order_meal.chef_meal_event else None
            })
        
        print(f"[DEBUG] OrderSerializer: Finished price_breakdown for Order id={obj.id}. Calculated Total: {calculated_total}") # Added print
        return breakdown

    def get_total_price(self, obj):
        # Recalculate from OrderMeals using get_price method
        calculated_total = Decimal('0.00')
        for order_meal in obj.ordermeal_set.all():
             unit_price = order_meal.get_price()
             quantity = order_meal.quantity
             # Ensure quantity is at least 1
             if quantity is None or quantity < 1:
                 quantity = 1
             # Ensure unit_price is a Decimal
             if not isinstance(unit_price, Decimal):
                unit_price = Decimal(str(unit_price)) # Convert safely
                
             calculated_total += (unit_price * quantity)
             
        # --- Print in get_total_price ---
        print(f"[DEBUG] OrderSerializer: get_total_price for Order id={obj.id}. Calculated Total: {calculated_total}")
        print(f"[DEBUG]   - Value from obj.total_price (if exists): {getattr(obj, 'total_price', 'N/A')}") 
        # --- End Print ---

        # Return the recalculated total, formatted as a string
        return str(calculated_total.quantize(Decimal('0.01')))

    def to_representation(self, instance):
        print(f"[DEBUG] OrderSerializer: Starting to_representation for Order id={instance.id}") # Added print
        data = super().to_representation(instance)
        # --- Print final values in to_representation ---
        print(f"[DEBUG] OrderSerializer: Final 'total_price' in representation for Order id={instance.id}: {data.get('total_price')}")
        print(f"[DEBUG] OrderSerializer: Final 'chef_meal_orders' count in representation for Order id={instance.id}: {len(data.get('chef_meal_orders', []))}")
        print(f"[DEBUG] OrderSerializer: Final 'price_breakdown' in representation for Order id={instance.id}: {data.get('price_breakdown')}")
        # --- End Print ---
        return data

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

class ChefMealOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChefMealOrder
        fields = ['meal_event', 'quantity', 'special_requests']
    
    def validate_meal_event(self, value):
        if not value.is_available_for_orders():
            raise serializers.ValidationError("This meal event is not available for orders")
        return value
    
    def create(self, validated_data):
        # Get quantity from request data or set default to 1
        quantity = validated_data.get('quantity', 1)
        
        # Create the order
        order = ChefMealOrder.objects.create(
            meal_event=validated_data['meal_event'],
            customer=validated_data['customer'],
            quantity=quantity,  # Store the quantity
            # Calculate total amount based on quantity
            total_amount=validated_data['meal_event'].current_price * quantity,
            status='placed',
            payment_status='pending'
        )
        
        return order

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

# <<< START: New Serializer for Chef Dashboard Orders >>>
class ChefReceivedOrderMealSerializer(serializers.ModelSerializer):
    """Serializer for individual meal items within a received order for the chef dashboard."""
    meal_name = serializers.CharField(source='meal.name', read_only=True)
    # Use the price from the linked event if available, otherwise meal price
    price = serializers.SerializerMethodField()

    class Meta:
        model = OrderMeal
        fields = ['meal_name', 'quantity', 'price']

    def get_price(self, obj):
        # Prioritize linked event price
        if hasattr(obj, 'chef_meal_event') and obj.chef_meal_event and obj.chef_meal_event.current_price is not None:
            return obj.chef_meal_event.current_price
        # Fallback to meal's price
        elif obj.meal and obj.meal.price is not None:
            return obj.meal.price
        return decimal.Decimal('0.00') # Default if no price found

class ChefReceivedOrderSerializer(serializers.ModelSerializer):
    """Serializer for orders received by a chef, suitable for the dashboard."""
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    # Filter meals to show only those belonging to the requesting chef
    meals_for_chef = serializers.SerializerMethodField()
    total_value_for_chef = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_date', 'updated_at', 'status', 'is_paid',
            'customer_username', 'customer_name',
            'meals_for_chef', 'total_value_for_chef'
            # Add other fields relevant to the chef's view if needed
        ]

    def get_meals_for_chef(self, obj):
        # Get the chef from the context (passed from the view)
        chef = self.context.get('chef')
        if not chef:
            return []

        # Filter OrderMeal items linked to this chef for this specific order (obj)
        order_meals = OrderMeal.objects.filter(order=obj).filter(
            # Check both meal chef and linked event chef
            Q(meal__chef=chef) | Q(chef_meal_event__chef=chef)
        ).distinct().select_related('meal', 'chef_meal_event') # Optimize query

        serializer = ChefReceivedOrderMealSerializer(order_meals, many=True)
        return serializer.data

    def get_total_value_for_chef(self, obj):
        # Calculate the total value of items belonging to this chef in this order
        chef = self.context.get('chef')
        if not chef:
            return decimal.Decimal('0.00')

        total = decimal.Decimal('0.00')
        order_meals = OrderMeal.objects.filter(
            order=obj).filter(
            Q(meal__chef=chef) | Q(chef_meal_event__chef=chef)
        ).distinct().select_related('meal', 'chef_meal_event')

        for om in order_meals:
            price = decimal.Decimal('0.00')
            # Prioritize linked event price
            if hasattr(om, 'chef_meal_event') and om.chef_meal_event and om.chef_meal_event.current_price is not None:
                price = om.chef_meal_event.current_price
            # Fallback to meal's price
            elif om.meal and om.meal.price is not None:
                price = om.meal.price

            total += (price * om.quantity)
        return total

# <<< END: New Serializer >>>
