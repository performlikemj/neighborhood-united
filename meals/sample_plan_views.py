"""
DEPRECATED: Sample Plan Preview API endpoints.

As of December 2024, the sample meal plan preview is now generated client-side
in frontend/src/data/sampleMeals.js for instant, live updates during onboarding.

These endpoints are kept for backwards compatibility with users who may have
already generated plans, but are no longer called by the frontend.

Safe to remove after confirming no active usage via server logs.

Original purpose:
Provides endpoints for generating and retrieving one-time sample meal plan previews
for users without chef access (Chef Preview Mode).
"""
import logging
from django.utils import timezone
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.models import SamplePlanPreview

logger = logging.getLogger(__name__)

# Days of the week for meal plan structure
DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner']


def _get_user_preferences(user):
    """Extract user preferences for meal plan generation."""
    preferences = {
        'dietary_preferences': [],
        'allergies': [],
        'custom_allergies': [],
        'household_size': getattr(user, 'household_member_count', 1) or 1,
        'measurement_system': getattr(user, 'measurement_system', 'METRIC'),
    }
    
    # Get dietary preferences
    try:
        dietary_prefs = user.dietary_preferences.all()
        preferences['dietary_preferences'] = [p.name for p in dietary_prefs]
    except Exception:
        pass
    
    # Get custom dietary preferences
    try:
        custom_prefs = user.custom_dietary_preferences.all()
        if custom_prefs:
            preferences['dietary_preferences'].extend([p.name for p in custom_prefs])
    except Exception:
        pass
    
    # Get allergies
    allergies = getattr(user, 'allergies', None)
    if allergies and isinstance(allergies, list):
        preferences['allergies'] = [a for a in allergies if a and a != 'None']
    
    # Get custom allergies
    custom_allergies = getattr(user, 'custom_allergies', None)
    if custom_allergies and isinstance(custom_allergies, list):
        preferences['custom_allergies'] = [a for a in custom_allergies if a]
    
    return preferences


def _generate_sample_meals(preferences):
    """Generate a sample meal plan based on user preferences.
    
    This creates a realistic-looking 7-day meal plan tailored to the user's
    dietary preferences and allergies. This is a preview/teaser, not meant
    for actual meal preparation.
    
    In the future, this could use AI to generate more personalized plans.
    For now, we use curated sample meals that respect dietary restrictions.
    """
    dietary_prefs = set(preferences.get('dietary_preferences', []))
    allergies = set(preferences.get('allergies', []) + preferences.get('custom_allergies', []))
    household_size = preferences.get('household_size', 1)
    
    # Base meal templates - these will be filtered based on preferences
    # Each meal has tags for dietary compatibility
    sample_meals = {
        'Breakfast': [
            {
                'name': 'Greek Yogurt Parfait with Fresh Berries',
                'description': 'Creamy Greek yogurt layered with seasonal berries, honey, and crunchy granola.',
                'tags': ['Vegetarian', 'High-Protein'],
                'avoid_allergies': ['Milk']
            },
            {
                'name': 'Avocado Toast with Poached Eggs',
                'description': 'Whole grain toast topped with mashed avocado, perfectly poached eggs, and microgreens.',
                'tags': ['Vegetarian', 'High-Protein'],
                'avoid_allergies': ['Egg', 'Wheat', 'Gluten']
            },
            {
                'name': 'Overnight Oats with Maple and Walnuts',
                'description': 'Creamy oats soaked overnight with almond milk, maple syrup, and toasted walnuts.',
                'tags': ['Vegetarian', 'Vegan', 'Dairy-Free'],
                'avoid_allergies': ['Tree nuts', 'Gluten']
            },
            {
                'name': 'Spinach and Mushroom Omelette',
                'description': 'Fluffy three-egg omelette filled with sautéed spinach, mushrooms, and herbs.',
                'tags': ['Vegetarian', 'Keto', 'High-Protein', 'Gluten-Free'],
                'avoid_allergies': ['Egg']
            },
            {
                'name': 'Fresh Fruit Bowl with Coconut',
                'description': 'A colorful mix of seasonal fruits topped with shredded coconut and lime zest.',
                'tags': ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'Paleo'],
                'avoid_allergies': []
            },
            {
                'name': 'Shakshuka with Crusty Bread',
                'description': 'Eggs poached in spiced tomato sauce with bell peppers, served with warm bread.',
                'tags': ['Vegetarian', 'Halal'],
                'avoid_allergies': ['Egg', 'Wheat', 'Gluten']
            },
            {
                'name': 'Chia Seed Pudding with Mango',
                'description': 'Chia seeds soaked in coconut milk, layered with fresh mango and passion fruit.',
                'tags': ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free'],
                'avoid_allergies': []
            },
        ],
        'Lunch': [
            {
                'name': 'Mediterranean Quinoa Bowl',
                'description': 'Fluffy quinoa with cucumber, tomatoes, olives, feta cheese, and lemon dressing.',
                'tags': ['Vegetarian', 'Gluten-Free', 'High-Protein'],
                'avoid_allergies': ['Milk']
            },
            {
                'name': 'Grilled Chicken Caesar Salad',
                'description': 'Romaine lettuce with grilled chicken, parmesan, croutons, and creamy Caesar dressing.',
                'tags': ['High-Protein', 'Halal'],
                'avoid_allergies': ['Milk', 'Egg', 'Wheat', 'Gluten', 'Fish']
            },
            {
                'name': 'Asian Vegetable Stir-Fry with Rice',
                'description': 'Crisp vegetables in ginger-soy sauce served over steamed jasmine rice.',
                'tags': ['Vegan', 'Vegetarian', 'Dairy-Free'],
                'avoid_allergies': ['Soy']
            },
            {
                'name': 'Roasted Vegetable Wrap',
                'description': 'Warm tortilla filled with roasted vegetables, hummus, and fresh herbs.',
                'tags': ['Vegan', 'Vegetarian', 'Dairy-Free'],
                'avoid_allergies': ['Wheat', 'Gluten', 'Sesame']
            },
            {
                'name': 'Lentil Soup with Herbs',
                'description': 'Hearty red lentil soup with carrots, celery, and aromatic spices.',
                'tags': ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'High-Protein'],
                'avoid_allergies': ['Celery']
            },
            {
                'name': 'Tuna Niçoise Salad',
                'description': 'Classic French salad with seared tuna, green beans, potatoes, olives, and eggs.',
                'tags': ['Pescatarian', 'Gluten-Free', 'High-Protein', 'Dairy-Free'],
                'avoid_allergies': ['Fish', 'Egg']
            },
            {
                'name': 'Falafel Bowl with Tahini',
                'description': 'Crispy falafel with hummus, tabbouleh, pickled vegetables, and tahini drizzle.',
                'tags': ['Vegan', 'Vegetarian', 'Dairy-Free', 'Halal'],
                'avoid_allergies': ['Wheat', 'Gluten', 'Sesame', 'Chickpeas']
            },
        ],
        'Dinner': [
            {
                'name': 'Herb-Crusted Salmon with Asparagus',
                'description': 'Wild-caught salmon with a herb crust, served with roasted asparagus and lemon.',
                'tags': ['Pescatarian', 'Gluten-Free', 'High-Protein', 'Keto', 'Paleo'],
                'avoid_allergies': ['Fish']
            },
            {
                'name': 'Chicken Tikka Masala with Basmati Rice',
                'description': 'Tender chicken in aromatic tomato-cream sauce, served with fluffy basmati rice.',
                'tags': ['High-Protein', 'Halal'],
                'avoid_allergies': ['Milk']
            },
            {
                'name': 'Vegetable Pad Thai',
                'description': 'Rice noodles with crispy tofu, vegetables, peanuts, and tangy tamarind sauce.',
                'tags': ['Vegan', 'Vegetarian', 'Dairy-Free'],
                'avoid_allergies': ['Peanuts', 'Soy']
            },
            {
                'name': 'Grilled Lamb Chops with Mint',
                'description': 'Perfectly grilled lamb chops with mint yogurt sauce and roasted potatoes.',
                'tags': ['High-Protein', 'Halal', 'Gluten-Free'],
                'avoid_allergies': ['Milk']
            },
            {
                'name': 'Eggplant Parmesan',
                'description': 'Breaded eggplant layered with marinara sauce and melted mozzarella cheese.',
                'tags': ['Vegetarian'],
                'avoid_allergies': ['Milk', 'Wheat', 'Gluten', 'Egg']
            },
            {
                'name': 'Shrimp Scampi with Linguine',
                'description': 'Succulent shrimp in garlic butter sauce tossed with linguine and fresh parsley.',
                'tags': ['Pescatarian', 'High-Protein'],
                'avoid_allergies': ['Shellfish', 'Wheat', 'Gluten', 'Milk']
            },
            {
                'name': 'Stuffed Bell Peppers',
                'description': 'Bell peppers filled with seasoned rice, black beans, corn, and melted cheese.',
                'tags': ['Vegetarian', 'Gluten-Free'],
                'avoid_allergies': ['Milk']
            },
            {
                'name': 'Thai Green Curry with Tofu',
                'description': 'Creamy coconut curry with crispy tofu, bamboo shoots, and Thai basil.',
                'tags': ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free'],
                'avoid_allergies': ['Soy']
            },
            {
                'name': 'Beef Bulgogi with Kimchi',
                'description': 'Korean-style marinated beef with steamed rice and traditional kimchi.',
                'tags': ['High-Protein', 'Dairy-Free'],
                'avoid_allergies': ['Soy', 'Wheat', 'Gluten']
            },
        ]
    }
    
    def is_meal_compatible(meal, dietary_prefs, allergies):
        """Check if a meal is compatible with user's dietary preferences and allergies."""
        # Check allergies first
        for allergy in allergies:
            if allergy in meal.get('avoid_allergies', []):
                return False
        
        # If no dietary preferences, all meals are compatible
        if not dietary_prefs:
            return True
        
        # Check if meal has at least one matching dietary tag
        meal_tags = set(meal.get('tags', []))
        return bool(dietary_prefs & meal_tags)
    
    # Generate the meal plan
    meals = []
    used_meals = set()  # Track used meal names to avoid repetition
    
    for day in DAYS_OF_WEEK:
        for meal_type in MEAL_TYPES:
            available_meals = [
                m for m in sample_meals[meal_type]
                if m['name'] not in used_meals and is_meal_compatible(m, dietary_prefs, allergies)
            ]
            
            # If no compatible meals, fall back to any meal not yet used
            if not available_meals:
                available_meals = [
                    m for m in sample_meals[meal_type]
                    if m['name'] not in used_meals
                ]
            
            # If still no meals (all used), allow repeats
            if not available_meals:
                available_meals = sample_meals[meal_type]
            
            # Select a meal (cycle through to get variety)
            meal_index = (DAYS_OF_WEEK.index(day) + MEAL_TYPES.index(meal_type)) % len(available_meals)
            selected_meal = available_meals[meal_index]
            
            used_meals.add(selected_meal['name'])
            
            meals.append({
                'day': day,
                'meal_type': meal_type,
                'meal_name': selected_meal['name'],
                'meal_description': selected_meal['description'],
                'servings': household_size
            })
    
    return meals


def _generate_week_summary(preferences, meals):
    """Generate a summary of the sample week."""
    dietary_prefs = preferences.get('dietary_preferences', [])
    household_size = preferences.get('household_size', 1)
    
    summary_parts = []
    
    if household_size > 1:
        summary_parts.append(f"Meals planned for {household_size} people")
    
    if dietary_prefs:
        prefs_str = ', '.join(dietary_prefs[:3])
        if len(dietary_prefs) > 3:
            prefs_str += f' and {len(dietary_prefs) - 3} more'
        summary_parts.append(f"Tailored to your {prefs_str} preferences")
    
    summary_parts.append("21 meals across 7 days")
    summary_parts.append("Balanced variety of breakfast, lunch, and dinner options")
    
    return '. '.join(summary_parts) + '.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sample_plan(request):
    """Get the user's existing sample meal plan preview.
    
    Returns:
        - If plan exists: the cached sample plan data
        - If no plan: 404 with instructions to generate one
    """
    user = request.user
    
    try:
        preview = SamplePlanPreview.objects.get(user=user)
        return Response({
            'has_plan': True,
            'plan_data': preview.plan_data,
            'preferences_snapshot': preview.preferences_snapshot,
            'created_at': preview.created_at.isoformat()
        })
    except SamplePlanPreview.DoesNotExist:
        return Response({
            'has_plan': False,
            'message': 'No sample plan generated yet. Use POST to generate one.'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_sample_plan(request):
    """Generate a one-time sample meal plan preview.
    
    This endpoint can only be called once per user. Subsequent calls will
    return an error directing the user to GET the existing plan.
    
    Request body (optional):
        {
            "force_regenerate": bool  # Admin override to regenerate (not implemented yet)
        }
    
    Returns:
        {
            'success': bool,
            'plan_data': { ... },
            'preferences_snapshot': { ... },
            'created_at': str
        }
    """
    user = request.user
    
    # Check if user already has a sample plan
    if user.sample_plan_generated:
        try:
            existing = SamplePlanPreview.objects.get(user=user)
            return Response({
                'success': False,
                'error': 'Sample plan already generated',
                'message': 'You have already generated your sample meal plan preview. Use GET to retrieve it.',
                'has_plan': True,
                'plan_data': existing.plan_data,
                'created_at': existing.created_at.isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        except SamplePlanPreview.DoesNotExist:
            # Flag set but no plan - allow regeneration
            pass
    
    # Get user preferences
    preferences = _get_user_preferences(user)
    
    # Generate sample meals
    try:
        meals = _generate_sample_meals(preferences)
        week_summary = _generate_week_summary(preferences, meals)
        
        plan_data = {
            'meals': meals,
            'week_summary': week_summary,
            'generated_for': {
                'dietary_preferences': preferences['dietary_preferences'],
                'allergies': preferences['allergies'] + preferences['custom_allergies'],
                'household_size': preferences['household_size']
            }
        }
        
        # Save the preview
        preview, created = SamplePlanPreview.objects.update_or_create(
            user=user,
            defaults={
                'plan_data': plan_data,
                'preferences_snapshot': preferences
            }
        )
        
        # Mark user as having generated a sample plan
        user.sample_plan_generated = True
        user.sample_plan_generated_at = timezone.now()
        user.save(update_fields=['sample_plan_generated', 'sample_plan_generated_at'])
        
        logger.info(f"Generated sample plan preview for user {user.id}")
        
        return Response({
            'success': True,
            'plan_data': plan_data,
            'preferences_snapshot': preferences,
            'created_at': preview.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.exception(f"Failed to generate sample plan for user {user.id}: {e}")
        return Response({
            'success': False,
            'error': 'Failed to generate sample plan',
            'message': 'An error occurred while generating your sample meal plan. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sample_plan_status(request):
    """Check the status of user's sample plan.
    
    Returns:
        {
            'has_generated': bool,
            'generated_at': str | None,
            'can_generate': bool
        }
    """
    user = request.user
    
    has_generated = bool(user.sample_plan_generated)
    generated_at = None
    
    if user.sample_plan_generated_at:
        generated_at = user.sample_plan_generated_at.isoformat()
    
    return Response({
        'has_generated': has_generated,
        'generated_at': generated_at,
        'can_generate': not has_generated
    })

