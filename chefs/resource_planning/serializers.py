"""
Serializers for Chef Resource Planning API.
"""
from rest_framework import serializers

from chefs.resource_planning.models import (
    ChefPrepPlan,
    ChefPrepPlanCommitment,
    ChefPrepPlanItem,
    RecipeIngredient,
)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Serializer for structured recipe ingredients."""
    
    class Meta:
        model = RecipeIngredient
        fields = [
            'id',
            'dish',
            'name',
            'quantity',
            'unit',
            'notes',
            'shelf_life_days',
            'storage_type',
            'shelf_life_updated_at',
        ]
        read_only_fields = ['id', 'shelf_life_days', 'shelf_life_updated_at']


class ChefPrepPlanItemSerializer(serializers.ModelSerializer):
    """Serializer for prep plan shopping list items."""
    
    class Meta:
        model = ChefPrepPlanItem
        fields = [
            'id',
            'ingredient_name',
            'total_quantity',
            'unit',
            'shelf_life_days',
            'storage_type',
            'earliest_use_date',
            'latest_use_date',
            'suggested_purchase_date',
            'timing_status',
            'timing_notes',
            'meals_using',
            'is_purchased',
            'purchased_date',
            'purchased_quantity',
        ]
        read_only_fields = [
            'id',
            'ingredient_name',
            'total_quantity',
            'unit',
            'shelf_life_days',
            'storage_type',
            'earliest_use_date',
            'latest_use_date',
            'suggested_purchase_date',
            'timing_status',
            'timing_notes',
            'meals_using',
        ]


class ChefPrepPlanCommitmentSerializer(serializers.ModelSerializer):
    """Serializer for prep plan commitments (meal plans, events, service orders)."""
    
    commitment_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ChefPrepPlanCommitment
        fields = [
            'id',
            'commitment_type',
            'commitment_type_display',
            'chef_meal_plan',
            'meal_event',
            'service_order',
            'service_date',
            'servings',
            'meal_name',
            'customer_name',
        ]
        read_only_fields = fields
    
    def get_commitment_type_display(self, obj):
        return obj.get_commitment_type_display()


class ChefPrepPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing prep plans."""
    
    class Meta:
        model = ChefPrepPlan
        fields = [
            'id',
            'plan_start_date',
            'plan_end_date',
            'generated_at',
            'status',
            'total_meals',
            'total_servings',
            'unique_ingredients',
        ]
        read_only_fields = fields


class ChefPrepPlanDetailSerializer(serializers.ModelSerializer):
    """Full serializer for prep plan details."""
    
    items = ChefPrepPlanItemSerializer(many=True, read_only=True)
    commitments = ChefPrepPlanCommitmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChefPrepPlan
        fields = [
            'id',
            'plan_start_date',
            'plan_end_date',
            'generated_at',
            'updated_at',
            'shopping_list',
            'batch_suggestions',
            'total_meals',
            'total_servings',
            'unique_ingredients',
            'status',
            'notes',
            'items',
            'commitments',
        ]
        read_only_fields = [
            'id',
            'generated_at',
            'updated_at',
            'shopping_list',
            'batch_suggestions',
            'total_meals',
            'total_servings',
            'unique_ingredients',
            'items',
            'commitments',
        ]


class ChefPrepPlanCreateSerializer(serializers.Serializer):
    """Serializer for creating a new prep plan."""
    
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    
    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be on or after start date.'
            })
        return data


class ShoppingListItemSerializer(serializers.Serializer):
    """Serializer for a single shopping list item."""
    
    id = serializers.IntegerField(read_only=True)
    ingredient = serializers.CharField()
    quantity = serializers.FloatField()
    unit = serializers.CharField()
    purchase_by = serializers.DateField()
    shelf_life_days = serializers.IntegerField()
    storage = serializers.CharField()
    timing_status = serializers.CharField()
    timing_notes = serializers.CharField(required=False)
    meals = serializers.ListField(child=serializers.DictField())
    is_purchased = serializers.BooleanField()


class ShoppingListByDateSerializer(serializers.Serializer):
    """Serializer for shopping list grouped by date."""
    
    # Dynamic keys (dates), each containing a list of items
    # This is handled in the view by returning dict directly


class BatchSuggestionSerializer(serializers.Serializer):
    """Serializer for a batch cooking suggestion."""
    
    ingredient = serializers.CharField()
    total_quantity = serializers.FloatField()
    unit = serializers.CharField()
    suggestion = serializers.CharField()
    prep_day = serializers.CharField()
    meals_covered = serializers.ListField(child=serializers.CharField())


class BatchSuggestionsSerializer(serializers.Serializer):
    """Serializer for batch suggestions response."""
    
    suggestions = BatchSuggestionSerializer(many=True)
    general_tips = serializers.ListField(child=serializers.CharField())


class MarkPurchasedSerializer(serializers.Serializer):
    """Serializer for marking items as purchased."""
    
    item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1
    )
    purchased_date = serializers.DateField(required=False)
    
    def validate_item_ids(self, value):
        # Will be validated against actual items in the view
        return value


class ShelfLifeLookupSerializer(serializers.Serializer):
    """Serializer for shelf life lookup requests."""
    
    ingredients = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=True,
        min_length=1,
        max_length=50
    )
    storage_preference = serializers.ChoiceField(
        choices=['refrigerated', 'frozen', 'pantry', 'counter'],
        required=False
    )


class ShelfLifeResultSerializer(serializers.Serializer):
    """Serializer for shelf life lookup results."""
    
    ingredient_name = serializers.CharField()
    shelf_life_days = serializers.IntegerField()
    storage_type = serializers.CharField()
    notes = serializers.CharField(allow_null=True)

