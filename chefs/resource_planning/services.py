"""
Chef Prep Plan Generation Service

Provides comprehensive meal planning and resource optimization for chefs:
- Aggregates upcoming commitments (meal events, service orders)
- Generates consolidated shopping lists with timing suggestions
- Provides batch cooking recommendations to reduce waste
"""
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from pydantic import BaseModel, Field

from chefs.resource_planning.models import (
    ChefPrepPlan,
    ChefPrepPlanCommitment,
    ChefPrepPlanItem,
    RecipeIngredient,
)
from chefs.resource_planning.shelf_life import (
    get_ingredient_shelf_lives,
    get_default_shelf_life,
)

logger = logging.getLogger(__name__)


# Pydantic schemas for AI responses
class EstimatedIngredient(BaseModel):
    """AI-estimated ingredient with quantity."""
    name: str = Field(..., description="Ingredient name")
    quantity: float = Field(..., description="Estimated quantity needed")
    unit: str = Field(..., description="Unit of measurement")


class EstimatedIngredientsResponse(BaseModel):
    """Response containing estimated ingredients for a dish."""
    ingredients: List[EstimatedIngredient]


class BatchSuggestion(BaseModel):
    """A batch cooking suggestion."""
    ingredient: str = Field(..., description="Ingredient to batch prep")
    total_quantity: float = Field(..., description="Total quantity across meals")
    unit: str = Field(..., description="Unit of measurement")
    suggestion: str = Field(..., description="Specific batch cooking recommendation")
    prep_day: str = Field(..., description="Recommended prep day")
    meals_covered: List[str] = Field(..., description="Meals this batch covers")


class BatchSuggestionsResponse(BaseModel):
    """Response containing batch cooking suggestions."""
    suggestions: List[BatchSuggestion]
    general_tips: List[str] = Field(default_factory=list, description="General meal prep tips")


@dataclass
class Commitment:
    """Unified representation of a chef's commitment (meal plan, event, or service order)."""
    commitment_type: str  # 'client_meal_plan', 'meal_event', or 'service_order'
    service_date: date
    servings: int
    meal_name: str
    chef_meal_plan_id: Optional[int] = None
    meal_event_id: Optional[int] = None
    service_order_id: Optional[int] = None
    customer_name: Optional[str] = None
    dishes: List[Dict] = None  # List of dish info with ingredients
    
    def __post_init__(self):
        if self.dishes is None:
            self.dishes = []


@dataclass
class AggregatedIngredient:
    """Aggregated ingredient across multiple meals."""
    name: str
    total_quantity: Decimal
    unit: str
    meals_using: List[Dict]  # [{name, date, quantity}]
    earliest_use: date
    latest_use: date
    shelf_life_days: Optional[int] = None
    storage_type: str = 'refrigerated'


def _get_groq_client():
    """Lazy Groq client factory."""
    try:
        from groq import Groq
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key:
            return Groq(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to create Groq client: {e}")
    return None


def get_upcoming_commitments(
    chef,
    start_date: date,
    end_date: date
) -> List[Commitment]:
    """
    Get all upcoming meal commitments for a chef including:
    - ChefMealPlan: Meal plans created for clients (primary workflow)
    - ChefMealEvent: Public meal events with customer orders
    - ChefServiceOrder: Booked service appointments
    
    Args:
        chef: Chef model instance
        start_date: Start of planning window
        end_date: End of planning window
        
    Returns:
        List of Commitment objects sorted by date
    """
    from meals.models import ChefMealEvent, ChefMealOrder, ChefMealPlan, ChefMealPlanDay, ChefMealPlanItem
    from chef_services.models import ChefServiceOrder
    
    commitments = []
    
    # =========================================================================
    # 1. CHEF MEAL PLANS (Primary workflow - meal plans for clients)
    # =========================================================================
    chef_meal_plans = ChefMealPlan.objects.filter(
        chef=chef,
        status__in=['draft', 'published'],  # Include drafts so chef can plan ahead
        start_date__lte=end_date,
        end_date__gte=start_date
    ).prefetch_related(
        'days__items__meal__dishes__ingredients',
        'days__items__meal__meal_dishes',
        'customer'
    )
    
    for plan in chef_meal_plans:
        # Get all non-skipped days within the date range
        plan_days = plan.days.filter(
            date__gte=start_date,
            date__lte=end_date,
            is_skipped=False
        ).prefetch_related('items__meal__dishes__ingredients', 'items__meal__meal_dishes')
        
        for day in plan_days:
            for item in day.items.all():
                # Get servings - use item servings or default based on customer household
                servings = item.servings or 1
                
                # Try to get household size from customer
                if plan.customer:
                    household_size = getattr(plan.customer, 'household_member_count', 1) or 1
                    servings = max(servings, household_size)
                
                # Gather dish/ingredient information
                dishes = []
                meal_name = item.display_name
                
                if item.meal:
                    # This item links to a Meal object
                    # Get ingredients from the meal's dishes
                    for dish in item.meal.dishes.all():
                        dish_info = {
                            'name': dish.name,
                            'dish_id': dish.id,
                            'ingredients': []
                        }
                        
                        # Check for structured RecipeIngredients first
                        recipe_ingredients = RecipeIngredient.objects.filter(dish=dish)
                        if recipe_ingredients.exists():
                            for ri in recipe_ingredients:
                                dish_info['ingredients'].append({
                                    'name': ri.name,
                                    'quantity': float(ri.quantity),
                                    'unit': ri.unit
                                })
                        else:
                            # Fall back to basic M2M ingredients (no quantities)
                            for ingredient in dish.ingredients.all():
                                dish_info['ingredients'].append({
                                    'name': ingredient.name,
                                    'quantity': None,
                                    'unit': None
                                })
                        
                        if dish_info['ingredients']:
                            dishes.append(dish_info)
                    
                    # Also check MealDish entries (composed dishes)
                    for meal_dish in item.meal.meal_dishes.all():
                        dish_info = {
                            'name': meal_dish.name,
                            'meal_dish_id': meal_dish.id,
                            'ingredients': []
                        }
                        
                        if meal_dish.ingredients:
                            if isinstance(meal_dish.ingredients, list):
                                for ing in meal_dish.ingredients:
                                    if isinstance(ing, dict):
                                        dish_info['ingredients'].append({
                                            'name': ing.get('name', ing.get('ingredient', str(ing))),
                                            'quantity': ing.get('quantity'),
                                            'unit': ing.get('unit')
                                        })
                                    else:
                                        dish_info['ingredients'].append({
                                            'name': str(ing),
                                            'quantity': None,
                                            'unit': None
                                        })
                        
                        if dish_info['ingredients']:
                            dishes.append(dish_info)
                    
                    # If meal has composed_dishes JSON field
                    if item.meal.composed_dishes:
                        for composed in item.meal.composed_dishes:
                            if isinstance(composed, dict):
                                dish_info = {
                                    'name': composed.get('name', 'Composed Dish'),
                                    'ingredients': []
                                }
                                for ing in (composed.get('ingredients') or []):
                                    if isinstance(ing, str):
                                        dish_info['ingredients'].append({
                                            'name': ing,
                                            'quantity': None,
                                            'unit': None
                                        })
                                    elif isinstance(ing, dict):
                                        dish_info['ingredients'].append({
                                            'name': ing.get('name', str(ing)),
                                            'quantity': ing.get('quantity'),
                                            'unit': ing.get('unit')
                                        })
                                if dish_info['ingredients']:
                                    dishes.append(dish_info)
                
                elif item.custom_name:
                    # Custom meal - use name/description as basis for AI estimation
                    dishes.append({
                        'name': item.custom_name,
                        'custom': True,
                        'description': item.custom_description,
                        'ingredients': []  # Will need AI estimation
                    })
                
                # FALLBACK: If we have a meal but no dishes with ingredients, use AI to generate
                # This handles meals created without structured dish/ingredient data
                # Check if we have dishes with actual ingredients
                has_ingredients = any(
                    len(d.get('ingredients', [])) > 0 for d in dishes
                )
                
                if not has_ingredients and meal_name:
                    # Clear empty dishes and add one that needs AI generation
                    description = ""
                    if item.meal and item.meal.description:
                        description = item.meal.description
                    elif item.custom_description:
                        description = item.custom_description
                    
                    dishes = [{
                        'name': meal_name,
                        'custom': True,
                        'description': description,
                        'needs_ingredient_generation': True,
                        'ingredients': []  # Will be generated by AI
                    }]
                
                customer_name = plan.customer.first_name or plan.customer.username if plan.customer else "Client"
                
                commitments.append(Commitment(
                    commitment_type='client_meal_plan',
                    service_date=day.date,
                    servings=servings,
                    meal_name=f"{meal_name} ({item.get_meal_type_display()})",
                    chef_meal_plan_id=plan.id,
                    customer_name=customer_name,
                    dishes=dishes
                ))
    
    # =========================================================================
    # 2. CHEF MEAL EVENTS (Public events with customer orders)
    # =========================================================================
    meal_events = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__gte=start_date,
        event_date__lte=end_date,
        status__in=['scheduled', 'open', 'closed', 'in_progress']
    ).select_related('meal').prefetch_related(
        'meal__dishes',
        'meal__dishes__ingredients',
        'meal__meal_dishes',
        'orders'
    )
    
    for event in meal_events:
        # Count confirmed orders
        confirmed_orders = event.orders.filter(
            status__in=['placed', 'confirmed']
        ).aggregate(total_qty=Sum('quantity'))
        
        total_servings = confirmed_orders.get('total_qty') or 0
        
        if total_servings > 0:
            # Gather dish information
            dishes = []
            
            # Chef-created dishes (M2M)
            for dish in event.meal.dishes.all():
                dish_info = {
                    'name': dish.name,
                    'dish_id': dish.id,
                    'ingredients': []
                }
                
                # Check for structured RecipeIngredients first
                recipe_ingredients = RecipeIngredient.objects.filter(dish=dish)
                if recipe_ingredients.exists():
                    for ri in recipe_ingredients:
                        dish_info['ingredients'].append({
                            'name': ri.name,
                            'quantity': float(ri.quantity),
                            'unit': ri.unit
                        })
                else:
                    # Fall back to basic M2M ingredients (no quantities)
                    for ingredient in dish.ingredients.all():
                        dish_info['ingredients'].append({
                            'name': ingredient.name,
                            'quantity': None,  # Will be estimated
                            'unit': None
                        })
                
                dishes.append(dish_info)
            
            # User-generated MealDish entries
            for meal_dish in event.meal.meal_dishes.all():
                dish_info = {
                    'name': meal_dish.name,
                    'meal_dish_id': meal_dish.id,
                    'ingredients': []
                }
                
                # MealDish.ingredients is a JSONField
                if meal_dish.ingredients:
                    if isinstance(meal_dish.ingredients, list):
                        for ing in meal_dish.ingredients:
                            if isinstance(ing, dict):
                                dish_info['ingredients'].append({
                                    'name': ing.get('name', ing.get('ingredient', str(ing))),
                                    'quantity': ing.get('quantity'),
                                    'unit': ing.get('unit')
                                })
                            else:
                                dish_info['ingredients'].append({
                                    'name': str(ing),
                                    'quantity': None,
                                    'unit': None
                                })
                
                dishes.append(dish_info)
            
            commitments.append(Commitment(
                commitment_type='meal_event',
                service_date=event.event_date,
                servings=total_servings,
                meal_name=event.meal.name if event.meal else f"Meal Event {event.id}",
                meal_event_id=event.id,
                dishes=dishes
            ))
    
    # =========================================================================
    # 3. SERVICE ORDERS (Booked service appointments)
    # =========================================================================
    service_orders = ChefServiceOrder.objects.filter(
        chef=chef,
        service_date__gte=start_date,
        service_date__lte=end_date,
        status='confirmed'
    ).select_related('offering')
    
    for order in service_orders:
        # Service orders don't have specific dishes - they're custom work
        # We'll note them but can't aggregate specific ingredients
        commitments.append(Commitment(
            commitment_type='service_order',
            service_date=order.service_date,
            servings=order.household_size,
            meal_name=order.offering.title if order.offering else "Service",
            service_order_id=order.id,
            dishes=[]  # Custom work - no predefined dishes
        ))
    
    # Sort by date
    commitments.sort(key=lambda c: c.service_date)
    
    return commitments


class GeneratedIngredient(BaseModel):
    """Schema for AI-generated ingredient with quantity."""
    name: str
    quantity: float
    unit: str


class GeneratedIngredientsResponse(BaseModel):
    """Response schema for generated ingredient list."""
    ingredients: List[GeneratedIngredient]


def generate_ingredients_for_meal(
    meal_name: str,
    description: str = "",
    servings: int = 4
) -> List[Dict]:
    """
    Use AI to generate a full ingredient list for a meal that has no structured data.
    
    Args:
        meal_name: Name of the meal/dish
        description: Optional description providing more context
        servings: Number of servings to estimate for
        
    Returns:
        List of ingredient dicts with name, quantity, unit
    """
    groq_client = _get_groq_client()
    if not groq_client:
        logger.warning(f"No Groq client - returning default ingredients for {meal_name}")
        return _get_default_ingredients_for_meal(meal_name)
    
    system_prompt = """You are a professional chef. Generate a realistic shopping list of ingredients for a meal.

For each ingredient, provide:
- name: the ingredient name (e.g., "quinoa", "chicken breast", "olive oil")
- quantity: numeric amount needed for the specified servings
- unit: appropriate unit (cups, lbs, oz, pieces, tablespoons, etc.)

Include all necessary ingredients - proteins, vegetables, grains, seasonings, oils, etc.
Be practical with quantities based on standard serving sizes.
Return ONLY valid JSON matching the schema."""

    context = f'Meal: "{meal_name}"'
    if description:
        context += f'\nDescription: {description}'
    context += f'\nServings: {servings}'

    user_prompt = f"""Generate a complete ingredient list for this meal:

{context}

Return JSON with an "ingredients" array containing name, quantity, and unit for each ingredient needed to prepare this meal."""

    try:
        response = groq_client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_ingredients",
                    "schema": GeneratedIngredientsResponse.model_json_schema(),
                },
            },
        )
        
        raw_json = response.choices[0].message.content or "{}"
        result = GeneratedIngredientsResponse.model_validate_json(raw_json)
        
        logger.info(f"Generated {len(result.ingredients)} ingredients for {meal_name}")
        
        return [
            {'name': ing.name, 'quantity': ing.quantity, 'unit': ing.unit}
            for ing in result.ingredients
        ]
        
    except Exception as e:
        logger.warning(f"Failed to generate ingredients for {meal_name}: {e}")
        return _get_default_ingredients_for_meal(meal_name)


def _get_default_ingredients_for_meal(meal_name: str) -> List[Dict]:
    """Fallback ingredient generation based on common meal patterns."""
    meal_lower = meal_name.lower()
    
    # Common meal patterns with typical ingredients
    if 'salad' in meal_lower:
        if 'quinoa' in meal_lower:
            return [
                {'name': 'quinoa', 'quantity': 1, 'unit': 'cups'},
                {'name': 'mixed greens', 'quantity': 4, 'unit': 'cups'},
                {'name': 'cucumber', 'quantity': 1, 'unit': 'medium'},
                {'name': 'cherry tomatoes', 'quantity': 1, 'unit': 'cup'},
                {'name': 'feta cheese', 'quantity': 0.5, 'unit': 'cup'},
                {'name': 'olive oil', 'quantity': 3, 'unit': 'tablespoons'},
                {'name': 'lemon juice', 'quantity': 2, 'unit': 'tablespoons'},
            ]
        return [
            {'name': 'mixed greens', 'quantity': 6, 'unit': 'cups'},
            {'name': 'vegetables (assorted)', 'quantity': 2, 'unit': 'cups'},
            {'name': 'dressing', 'quantity': 0.25, 'unit': 'cup'},
        ]
    
    if 'chicken' in meal_lower:
        return [
            {'name': 'chicken breast', 'quantity': 1.5, 'unit': 'lbs'},
            {'name': 'olive oil', 'quantity': 2, 'unit': 'tablespoons'},
            {'name': 'garlic', 'quantity': 3, 'unit': 'cloves'},
            {'name': 'salt', 'quantity': 1, 'unit': 'teaspoon'},
            {'name': 'pepper', 'quantity': 0.5, 'unit': 'teaspoon'},
        ]
    
    if 'pasta' in meal_lower:
        return [
            {'name': 'pasta', 'quantity': 1, 'unit': 'lb'},
            {'name': 'olive oil', 'quantity': 2, 'unit': 'tablespoons'},
            {'name': 'garlic', 'quantity': 3, 'unit': 'cloves'},
            {'name': 'parmesan cheese', 'quantity': 0.5, 'unit': 'cup'},
        ]
    
    if 'soup' in meal_lower or 'stew' in meal_lower:
        return [
            {'name': 'broth', 'quantity': 6, 'unit': 'cups'},
            {'name': 'vegetables (assorted)', 'quantity': 3, 'unit': 'cups'},
            {'name': 'protein (meat or beans)', 'quantity': 1, 'unit': 'lb'},
            {'name': 'onion', 'quantity': 1, 'unit': 'medium'},
            {'name': 'garlic', 'quantity': 3, 'unit': 'cloves'},
        ]
    
    # Generic fallback
    return [
        {'name': 'main ingredient', 'quantity': 1, 'unit': 'lb'},
        {'name': 'vegetables', 'quantity': 2, 'unit': 'cups'},
        {'name': 'seasonings', 'quantity': 1, 'unit': 'tablespoon'},
        {'name': 'cooking oil', 'quantity': 2, 'unit': 'tablespoons'},
    ]


def estimate_ingredient_quantities(
    dish_name: str,
    ingredient_names: List[str],
    servings: int = 4
) -> Dict[str, Dict]:
    """
    Use AI to estimate ingredient quantities for a dish.
    
    Args:
        dish_name: Name of the dish
        ingredient_names: List of ingredient names
        servings: Number of servings to estimate for
        
    Returns:
        Dict mapping ingredient name to {quantity, unit}
    """
    if not ingredient_names:
        return {}
    
    groq_client = _get_groq_client()
    if not groq_client:
        # Return default estimates
        return {
            name: {'quantity': servings * 0.25, 'unit': 'cups'}
            for name in ingredient_names
        }
    
    ingredients_list = ", ".join(ingredient_names)
    
    system_prompt = """You are a professional chef. Estimate realistic ingredient quantities.

For each ingredient, provide:
- quantity: numeric amount needed (for the specified servings)
- unit: appropriate unit (cups, grams, pieces, tablespoons, etc.)

Be practical and use common cooking measurements. Consider:
- Main proteins: typically 4-6 oz per serving
- Vegetables: typically 1/2 to 1 cup per serving
- Grains: typically 1/2 cup per serving
- Seasonings: typically measured in teaspoons/tablespoons

Return ONLY valid JSON matching the schema."""

    user_prompt = f"""Estimate ingredient quantities for making "{dish_name}" for {servings} servings.

Ingredients to estimate:
{ingredients_list}

Return JSON with an "ingredients" array containing name, quantity, and unit for each."""

    try:
        response = groq_client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "estimated_ingredients",
                    "schema": EstimatedIngredientsResponse.model_json_schema(),
                },
            },
        )
        
        raw_json = response.choices[0].message.content or "{}"
        result = EstimatedIngredientsResponse.model_validate_json(raw_json)
        
        return {
            ing.name.lower(): {'quantity': ing.quantity, 'unit': ing.unit}
            for ing in result.ingredients
        }
        
    except Exception as e:
        logger.warning(f"Failed to estimate quantities: {e}")
        return {
            name: {'quantity': servings * 0.25, 'unit': 'cups'}
            for name in ingredient_names
        }


def aggregate_ingredients(
    commitments: List[Commitment]
) -> Dict[str, AggregatedIngredient]:
    """
    Aggregate ingredients across all commitments.
    
    Groups by ingredient name (case-insensitive) and sums quantities.
    Estimates quantities where not provided.
    Generates ingredients for dishes without any structured data.
    
    Args:
        commitments: List of Commitment objects
        
    Returns:
        Dict mapping ingredient name to AggregatedIngredient
    """
    aggregated: Dict[str, Dict] = defaultdict(lambda: {
        'total_quantity': Decimal('0'),
        'unit': None,
        'meals_using': [],
        'dates': []
    })
    
    for commitment in commitments:
        for dish in commitment.dishes:
            current_ingredients = dish.get('ingredients', [])
            already_scaled_for_servings = False
            
            # If dish needs full ingredient generation (no structured data)
            if dish.get('needs_ingredient_generation') and not current_ingredients:
                logger.info(f"Generating ingredients for: {dish['name']}")
                generated = generate_ingredients_for_meal(
                    meal_name=dish['name'],
                    description=dish.get('description', ''),
                    servings=commitment.servings
                )
                current_ingredients = generated
                already_scaled_for_servings = True  # AI generation already factors in servings
            
            # Get or estimate ingredient quantities for existing ingredients without quantities
            ingredients_to_estimate = []
            
            for ing in current_ingredients:
                if ing.get('quantity') is None:
                    ingredients_to_estimate.append(ing['name'])
            
            # Estimate missing quantities (already includes serving scaling)
            estimates = {}
            if ingredients_to_estimate:
                estimates = estimate_ingredient_quantities(
                    dish['name'],
                    ingredients_to_estimate,
                    commitment.servings
                )
            
            # Aggregate each ingredient
            for ing in current_ingredients:
                name_key = ing['name'].lower().strip()
                
                # Get quantity and unit
                if ing.get('quantity') is not None:
                    # Only multiply by servings if quantities are per-serving (structured data)
                    # AI-generated quantities are already scaled
                    if already_scaled_for_servings:
                        quantity = Decimal(str(ing['quantity']))
                    else:
                        quantity = Decimal(str(ing['quantity'])) * commitment.servings
                    unit = ing.get('unit', 'units')
                else:
                    # Estimated quantities are already scaled for servings
                    est = estimates.get(name_key, {'quantity': 0.25, 'unit': 'cups'})
                    quantity = Decimal(str(est['quantity']))
                    unit = est['unit']
                
                agg = aggregated[name_key]
                agg['name'] = ing['name']  # Preserve original casing
                agg['total_quantity'] += quantity
                agg['meals_using'].append({
                    'name': f"{commitment.meal_name} - {dish['name']}",
                    'date': commitment.service_date.isoformat(),
                    'quantity': float(quantity)
                })
                agg['dates'].append(commitment.service_date)
                
                # Track unit (prefer first seen, but could add unit conversion later)
                if agg['unit'] is None:
                    agg['unit'] = unit
    
    # Convert to AggregatedIngredient objects
    result = {}
    for key, data in aggregated.items():
        dates = data['dates']
        result[key] = AggregatedIngredient(
            name=data.get('name', key),
            total_quantity=data['total_quantity'],
            unit=data['unit'] or 'units',
            meals_using=data['meals_using'],
            earliest_use=min(dates) if dates else date.today(),
            latest_use=max(dates) if dates else date.today()
        )
    
    return result


def calculate_shopping_timing(
    aggregated_ingredients: Dict[str, AggregatedIngredient],
    plan_start_date: date
) -> List[ChefPrepPlanItem]:
    """
    Calculate optimal purchase dates for each ingredient based on shelf life.
    
    Args:
        aggregated_ingredients: Dict of AggregatedIngredient objects
        plan_start_date: Start of the planning window
        
    Returns:
        List of ChefPrepPlanItem objects (not yet saved)
    """
    # Get shelf life for all ingredients in batch
    ingredient_names = list(aggregated_ingredients.keys())
    
    try:
        shelf_life_response = get_ingredient_shelf_lives(
            [agg.name for agg in aggregated_ingredients.values()]
        )
        shelf_life_map = {
            info.ingredient_name.lower(): info
            for info in shelf_life_response.ingredients
        }
    except Exception as e:
        logger.warning(f"Could not get shelf life from API: {e}")
        shelf_life_map = {}
    
    items = []
    today = date.today()
    
    for key, agg in aggregated_ingredients.items():
        # Get shelf life (from API or fallback)
        shelf_info = shelf_life_map.get(key)
        if shelf_info:
            shelf_life_days = shelf_info.shelf_life_days
            storage_type = shelf_info.storage_type
        else:
            defaults = get_default_shelf_life(agg.name)
            shelf_life_days = defaults['shelf_life_days']
            storage_type = defaults['storage_type']
        
        # Calculate suggested purchase date
        # Buy as late as possible while ensuring freshness for earliest use
        # Formula: purchase_date = earliest_use - shelf_life + buffer_days
        buffer_days = 1  # Safety buffer
        
        suggested_purchase = agg.earliest_use - timedelta(days=shelf_life_days - buffer_days)
        
        # Don't suggest buying in the past
        if suggested_purchase < today:
            suggested_purchase = today
        
        # Don't suggest buying before plan starts
        if suggested_purchase < plan_start_date:
            suggested_purchase = plan_start_date
        
        item = ChefPrepPlanItem(
            ingredient_name=agg.name,
            total_quantity=agg.total_quantity,
            unit=agg.unit,
            shelf_life_days=shelf_life_days,
            storage_type=storage_type,
            earliest_use_date=agg.earliest_use,
            latest_use_date=agg.latest_use,
            suggested_purchase_date=suggested_purchase,
            meals_using=agg.meals_using
        )
        
        # Calculate timing status
        item.calculate_timing_status()
        
        items.append(item)
    
    # Sort by purchase date
    items.sort(key=lambda x: (x.suggested_purchase_date, x.ingredient_name))
    
    return items


def generate_batch_suggestions(
    aggregated_ingredients: Dict[str, AggregatedIngredient],
    commitments: List[Commitment]
) -> BatchSuggestionsResponse:
    """
    Generate AI-powered batch cooking suggestions to optimize prep.
    
    Args:
        aggregated_ingredients: Dict of AggregatedIngredient objects
        commitments: List of commitments for context
        
    Returns:
        BatchSuggestionsResponse with suggestions and tips
    """
    groq_client = _get_groq_client()
    
    if not groq_client or not aggregated_ingredients:
        return BatchSuggestionsResponse(
            suggestions=[],
            general_tips=["Plan your prep day based on your busiest service days."]
        )
    
    # Build context for AI
    ingredients_summary = []
    for key, agg in aggregated_ingredients.items():
        meals = [m['name'] for m in agg.meals_using]
        ingredients_summary.append(
            f"- {agg.name}: {float(agg.total_quantity):.1f} {agg.unit} "
            f"(used in: {', '.join(set(meals))})"
        )
    
    meals_summary = []
    for c in commitments:
        meals_summary.append(f"- {c.meal_name}: {c.service_date.isoformat()}, {c.servings} servings")
    
    system_prompt = """You are a professional chef consultant helping optimize meal prep.

Analyze the ingredients and meals, then provide:
1. Batch cooking suggestions - identify ingredients that appear in multiple meals
   and can be prepped together to save time and reduce waste
2. General tips for efficient prep

For each suggestion, provide:
- ingredient: The ingredient to batch prep
- total_quantity: Total amount needed
- unit: Unit of measurement
- suggestion: Specific actionable recommendation
- prep_day: Recommended day to prep (e.g., "Monday" or "Day before first use")
- meals_covered: List of meals this prep covers

Focus on:
- Proteins that can be cooked in bulk
- Grains (rice, quinoa) that reheat well
- Vegetables that can be prepped ahead
- Sauces/marinades that can be made in batches

Return ONLY valid JSON matching the schema."""

    user_prompt = f"""Plan batch cooking for these upcoming meals:

MEALS:
{chr(10).join(meals_summary)}

INGREDIENTS NEEDED:
{chr(10).join(ingredients_summary)}

Provide batch cooking suggestions to optimize prep and reduce waste."""

    try:
        response = groq_client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "batch_suggestions",
                    "schema": BatchSuggestionsResponse.model_json_schema(),
                },
            },
        )
        
        raw_json = response.choices[0].message.content or "{}"
        return BatchSuggestionsResponse.model_validate_json(raw_json)
        
    except Exception as e:
        logger.warning(f"Failed to generate batch suggestions: {e}")
        return BatchSuggestionsResponse(
            suggestions=[],
            general_tips=[
                "Prep proteins in bulk at the start of the week.",
                "Cook grains like rice in large batches - they reheat well.",
                "Wash and chop vegetables ahead of time."
            ]
        )


@transaction.atomic
def generate_prep_plan(
    chef,
    start_date: date,
    end_date: date,
    notes: str = ""
) -> ChefPrepPlan:
    """
    Generate a complete prep plan for a chef's upcoming window.
    
    This is the main entry point that orchestrates the full planning process.
    
    Args:
        chef: Chef model instance
        start_date: Start of planning window
        end_date: End of planning window
        notes: Optional notes for the plan
        
    Returns:
        Created ChefPrepPlan instance with all related items
    """
    # Create the prep plan
    prep_plan = ChefPrepPlan.objects.create(
        chef=chef,
        plan_start_date=start_date,
        plan_end_date=end_date,
        status='draft',
        notes=notes
    )
    
    try:
        # Get commitments
        commitments = get_upcoming_commitments(chef, start_date, end_date)
        
        # Create commitment records
        for c in commitments:
            ChefPrepPlanCommitment.objects.create(
                prep_plan=prep_plan,
                commitment_type=c.commitment_type,
                chef_meal_plan_id=c.chef_meal_plan_id,
                meal_event_id=c.meal_event_id,
                service_order_id=c.service_order_id,
                service_date=c.service_date,
                servings=c.servings,
                meal_name=c.meal_name,
                customer_name=c.customer_name or ''
            )
        
        # Aggregate ingredients
        aggregated = aggregate_ingredients(commitments)
        
        # Calculate shopping timing
        plan_items = calculate_shopping_timing(aggregated, start_date)
        
        # Save items
        for item in plan_items:
            item.prep_plan = prep_plan
            item.save()
        
        # Generate batch suggestions
        batch_suggestions = generate_batch_suggestions(aggregated, commitments)
        
        # Update plan with summary data
        prep_plan.total_meals = len(commitments)
        prep_plan.total_servings = sum(c.servings for c in commitments)
        prep_plan.unique_ingredients = len(aggregated)
        prep_plan.batch_suggestions = batch_suggestions.model_dump()
        
        # Build shopping list JSON
        shopping_list = []
        for item in plan_items:
            shopping_list.append({
                'ingredient': item.ingredient_name,
                'quantity': float(item.total_quantity),
                'unit': item.unit,
                'purchase_by': item.suggested_purchase_date.isoformat(),
                'shelf_life_days': item.shelf_life_days,
                'storage': item.storage_type,
                'timing_status': item.timing_status,
                'meals': item.meals_using
            })
        
        prep_plan.shopping_list = shopping_list
        prep_plan.status = 'generated'
        prep_plan.save()
        
        logger.info(
            f"Generated prep plan {prep_plan.id} for chef {chef.id}: "
            f"{len(commitments)} commitments, {len(aggregated)} unique ingredients, "
            f"{len(plan_items)} shopping items"
        )
        
        # Debug: log commitment details
        for c in commitments:
            logger.info(f"  Commitment: {c.meal_name} on {c.service_date}, {len(c.dishes)} dishes")
            for d in c.dishes:
                logger.info(f"    Dish: {d.get('name')}, {len(d.get('ingredients', []))} ingredients, needs_gen={d.get('needs_ingredient_generation', False)}")
        
        return prep_plan
        
    except Exception as e:
        logger.error(f"Failed to generate prep plan: {e}")
        prep_plan.status = 'draft'
        prep_plan.notes = f"Generation failed: {str(e)}"
        prep_plan.save()
        raise


def get_shopping_list_by_date(prep_plan: ChefPrepPlan) -> Dict[str, List[Dict]]:
    """
    Get shopping list organized by purchase date.
    
    Args:
        prep_plan: ChefPrepPlan instance
        
    Returns:
        Dict mapping date string to list of items to purchase
    """
    items_by_date = defaultdict(list)
    
    for item in prep_plan.items.all().order_by('suggested_purchase_date'):
        date_key = item.suggested_purchase_date.isoformat()
        items_by_date[date_key].append({
            'id': item.id,
            'ingredient': item.ingredient_name,
            'quantity': float(item.total_quantity),
            'unit': item.unit,
            'shelf_life_days': item.shelf_life_days,
            'storage': item.storage_type,
            'timing_status': item.timing_status,
            'timing_notes': item.timing_notes,
            'earliest_use': item.earliest_use_date.isoformat(),
            'latest_use': item.latest_use_date.isoformat(),
            'meals': item.meals_using,
            'is_purchased': item.is_purchased
        })
    
    return dict(items_by_date)


def get_shopping_list_by_category(prep_plan: ChefPrepPlan) -> Dict[str, List[Dict]]:
    """
    Get shopping list organized by storage category.
    
    Args:
        prep_plan: ChefPrepPlan instance
        
    Returns:
        Dict mapping storage type to list of items
    """
    items_by_category = defaultdict(list)
    
    for item in prep_plan.items.all().order_by('ingredient_name'):
        items_by_category[item.storage_type].append({
            'id': item.id,
            'ingredient': item.ingredient_name,
            'quantity': float(item.total_quantity),
            'unit': item.unit,
            'purchase_by': item.suggested_purchase_date.isoformat(),
            'timing_status': item.timing_status,
            'is_purchased': item.is_purchased
        })
    
    # Order categories logically
    ordered = {}
    for cat in ['refrigerated', 'frozen', 'counter', 'pantry']:
        if cat in items_by_category:
            ordered[cat] = items_by_category[cat]
    
    return ordered







