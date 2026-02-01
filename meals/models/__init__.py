# meals/models/__init__.py
"""
Meals models package.

This package organizes the meal-related models into logical submodules:
- core: Ingredient, MealType, Dish, Meal, MealDish, Tag
- plans: MealPlan, MealPlanMeal, ShoppingList, Instruction, PantryItem, etc.
- chef_events: ChefMealEvent, ChefMealOrder, ChefMealReview, ChefMealPlan, etc.
- commerce: Cart, Order, OrderMeal, StripeConnectAccount, PaymentLog, etc.
- utility: DietaryPreference, CustomDietaryPreference, MealCompatibility, etc.

All models are re-exported here for backward compatibility.
Existing imports like `from meals.models import Meal` will continue to work.
"""

# Status constants (used across multiple models)
from .chef_events import (
    STATUS_COMPLETED,
    STATUS_CANCELLED,
    STATUS_SCHEDULED,
    STATUS_OPEN,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_PLACED,
    STATUS_CONFIRMED,
    STATUS_REFUNDED,
)

# Core models
from .core import (
    PostalCodeManager,
    DietaryPreferenceManager,
    Ingredient,
    MealType,
    Tag,
    Dish,
    Meal,
    MealDish,
)

# Utility models
from .utility import (
    clean_preference_name,
    DietaryPreference,
    CustomDietaryPreference,
    SystemUpdate,
    MealCompatibility,
    MealAllergenSafety,
)

# Plans models
from .plans import (
    MealPlan,
    MealPlanInstruction,
    MealPlanMeal,
    ShoppingList,
    Instruction,
    MealPlanThread,
    PantryItem,
    MealPlanMealPantryUsage,
    MealPlanBatchJob,
    MealPlanBatchRequest,
    SamplePlanPreview,
)

# Chef events models
from .chef_events import (
    ChefMealEvent,
    ChefMealOrder,
    ChefMealReview,
    ChefMealPlan,
    ChefMealPlanDay,
    ChefMealPlanItem,
    MealPlanSuggestion,
    MealPlanGenerationJob,
)

# Commerce models
from .commerce import (
    Cart,
    Order,
    OrderMeal,
    StripeConnectAccount,
    PlatformFeeConfig,
    PaymentLog,
    MealPlanReceipt,
)

# Re-export from other apps for backward compatibility
from custom_auth.models import CustomUser, Address
from chefs.models import Chef
from local_chefs.models import PostalCode, ChefPostalCode


# Define __all__ for explicit exports
__all__ = [
    # Status constants
    'STATUS_COMPLETED',
    'STATUS_CANCELLED',
    'STATUS_SCHEDULED',
    'STATUS_OPEN',
    'STATUS_CLOSED',
    'STATUS_IN_PROGRESS',
    'STATUS_PLACED',
    'STATUS_CONFIRMED',
    'STATUS_REFUNDED',
    
    # Core models
    'PostalCodeManager',
    'DietaryPreferenceManager',
    'Ingredient',
    'MealType',
    'Tag',
    'Dish',
    'Meal',
    'MealDish',
    
    # Utility models
    'clean_preference_name',
    'DietaryPreference',
    'CustomDietaryPreference',
    'SystemUpdate',
    'MealCompatibility',
    'MealAllergenSafety',
    
    # Plans models
    'MealPlan',
    'MealPlanInstruction',
    'MealPlanMeal',
    'ShoppingList',
    'Instruction',
    'MealPlanThread',
    'PantryItem',
    'MealPlanMealPantryUsage',
    'MealPlanBatchJob',
    'MealPlanBatchRequest',
    'SamplePlanPreview',
    
    # Chef events models
    'ChefMealEvent',
    'ChefMealOrder',
    'ChefMealReview',
    'ChefMealPlan',
    'ChefMealPlanDay',
    'ChefMealPlanItem',
    'MealPlanSuggestion',
    'MealPlanGenerationJob',
    
    # Commerce models
    'Cart',
    'Order',
    'OrderMeal',
    'StripeConnectAccount',
    'PlatformFeeConfig',
    'PaymentLog',
    'MealPlanReceipt',
    # Re-exported from other apps
    'CustomUser',
    'Address',
    'Chef',
    'PostalCode',
    'ChefPostalCode',
]
