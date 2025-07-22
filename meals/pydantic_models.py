# meals/pydantic_models.py
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Optional, Dict, Any, ClassVar
from enum import Enum

class DietaryPreference(str, Enum):
    VEGAN = "Vegan"
    VEGETARIAN = "Vegetarian"
    PESCATARIAN = "Pescatarian"
    GLUTEN_FREE = "Gluten-Free"
    KETO = "Keto"
    PALEO = "Paleo"
    HALAL = "Halal"
    KOSHER = "Kosher"
    LOW_CALORIE = "Low-Calorie"
    LOW_SODIUM = "Low-Sodium"
    HIGH_PROTEIN = "High-Protein"
    DAIRY_FREE = "Dairy-Free"
    NUT_FREE = "Nut-Free"
    RAW_FOOD = "Raw Food"
    WHOLE_30 = "Whole 30"
    LOW_FODMAP = "Low-FODMAP"
    DIABETIC_FRIENDLY = "Diabetic-Friendly"
    EVERYTHING = "Everything"

# Define the possible categories for shopping list items
class ShoppingCategory(str, Enum):
    PRODUCE = "Produce"
    DAIRY = "Dairy"
    MEAT = "Meat"
    BAKERY = "Bakery"
    BEVERAGES = "Beverages"
    FROZEN = "Frozen"
    GRAINS = "Grains"
    SNACKS = "Snacks"
    CONDIMENTS = "Condiments"
    MISC = "Miscellaneous"

class MealMacroInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    calories: float = Field(..., description="Total calories in kcal")
    protein: float = Field(..., description="Protein content in grams")
    carbohydrates: float = Field(..., description="Carbohydrate content in grams")
    fat: float = Field(..., description="Fat content in grams")
    fiber: Optional[float] = Field(..., description="Dietary fiber in grams")
    sugar: Optional[float] = Field(..., description="Sugar content in grams")
    sodium: Optional[float] = Field(..., description="Sodium content in mg")
    serving_size: str = Field(..., description="Serving size (e.g., '1 cup', '200g')")
    
    example: ClassVar[Dict[str, Any]] = {
        "calories": 350.5,
        "protein": 25.2,
        "carbohydrates": 30.5,
        "fat": 12.3,
        "fiber": 5.2,
        "sugar": 3.1,
        "sodium": 120.0,
        "serving_size": "1 cup (240g)"
    }

class YouTubeVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    title: str = Field(..., description="Title of the YouTube video")
    url: str = Field(..., description="Full URL to the YouTube video")
    channel: str = Field(..., description="Name of the YouTube channel")
    description: Optional[str] = Field(..., description="Brief description of the video content")
    duration: Optional[str] = Field(..., description="Duration of the video (if available)")
    
    example: ClassVar[Dict[str, Any]] = {
        "title": "Easy Chicken Stir Fry Recipe - Ready in 20 Minutes",
        "url": "https://www.youtube.com/watch?v=example123",
        "channel": "Cooking with Chef John",
        "description": "A quick and healthy chicken stir fry recipe perfect for weeknight dinners.",
        "duration": "10:25"
    }

class YouTubeVideoResults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    videos: List[YouTubeVideo] = Field(..., description="List of relevant YouTube videos")
    search_query: Optional[str] = Field(..., description="Search query used to find these videos")

# --- Pydantic Schemas for Meal Metadata --- 

class MealMetadata(BaseModel):
    macro_info: Optional[MealMacroInfo] = Field(..., description="Nutritional information for the meal")
    youtube_videos: Optional[YouTubeVideoResults] = Field(..., description="Links to relevant YouTube cooking videos")

class EmergencySupplyItem(BaseModel):
    item_name: str
    quantity_to_buy: str
    unit: Optional[str] = Field(..., description="Unit of measurement")
    notes: Optional[str] = Field(..., description="Additional notes")

    # Important: Don't include default values in the schema
    model_config = ConfigDict(extra="forbid")

class EmergencySupplyList(BaseModel):
    emergency_list: List[EmergencySupplyItem]
    notes: Optional[str] = Field(..., description="Additional notes")

    # Set the schema title and forbid extra properties at the top level.
    model_config = ConfigDict(title="EmergencySupplyList", extra="forbid")

    
# Define the possible meal types
class MealType(str, Enum):
    BREAKFAST = "Breakfast"
    LUNCH = "Lunch"
    DINNER = "Dinner"

class PantryUsageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pantry_item_name: str = Field(..., description="Exact name of the pantry item used.")
    quantity_used: Optional[str] = Field(
        ..., 
        description="Amount of this pantry item used, e.g. '2', '1.5', '0.5', 'To taste', etc."
    )
    unit: Optional[str] = Field(
        ...,
        description="Unit of measure for the used quantity, e.g. 'cup', 'teaspoon', 'each', etc."
    )
    notes: Optional[str] = Field(..., description="Any special notes about usage.")

# Define a Pydantic model for pantry item extraction
class PantryItemSchema(BaseModel):
    item_name: str = Field(..., description="The name of the pantry item")
    quantity: int = Field(1, description="The count/number of items (integer)")
    expiration_date: Optional[str] = Field(None, description="The expiration date in format YYYY-MM-DD, MM/DD/YYYY, or similar")
    item_type: str = Field("Canned", description="Either 'Canned' or 'Dry'")
    notes: Optional[str] = Field(None, description="Additional notes about the item")
    weight_per_unit: Optional[float] = Field(None, description="Weight or volume per unit, e.g. 2.0 for 2 liters or 16.0 for 16 ounces")
    weight_unit: Optional[str] = Field(None, description="Unit of measurement: 'oz', 'lb', 'g', or 'kg'")

    class Config:
        json_schema_extra = {
            "example": {
                "item_name": "Black Beans",
                "quantity": 3,
                "expiration_date": "2025-12-31",
                "item_type": "Canned",
                "notes": "Organic, low sodium",
                "weight_per_unit": 15.5,
                "weight_unit": "oz"
            }
        }
        
class ShoppingListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name: str
    ingredient: str
    quantity: str
    unit: str
    notes: Optional[str] = Field(..., description="Any special notes about the item.")
    category: str = Field(..., description="Category of the item.")

class ShoppingList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: List[ShoppingListItem]

class InstructionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_number: int
    description: str = Field(..., min_length=1, description="Detailed description of the step. Cannot be empty.")
    duration: Optional[str] = Field(..., description="Estimated duration. If not provided, defaults to 'N/A'.")

class Instructions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: List[InstructionStep]

class MealData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    dietary_preferences: List[str] = Field(..., description="One or more dietary preference tags.")
    meal_type: Optional[str] = Field(..., description="Type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')")
    is_chef_meal: bool = Field(
        ...,
        description="Indicates if this meal was created by a chef"
    )
    chef_name: Optional[str] = Field(
        ...,
        description="Name of the chef who created this meal, if applicable"
    )
    chef_meal_event_id: Optional[int] = Field(
        ...,
        description="ID of the chef meal event, if this is a chef meal"
    )
    used_pantry_items: List[str] = Field(
        ...,
        description="List of the user's expiring pantry items (in string form) actually used in this meal."
    )

class MealOutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal: MealData
    status: str
    message: str
    current_time: str

class MealPlanMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: str  # e.g., "Monday"
    meal_type: str  # e.g., "Breakfast"
    meal_name: str
    meal_description: Optional[str] = None
    is_chef_meal: bool = Field(
        ...,
        description="Indicates if this meal was created by a chef"
    )
    chef_name: Optional[str] = Field(
        ...,
        description="Name of the chef who created this meal, if applicable"
    )
    chef_meal_event_id: Optional[int] = Field(
        ...,
        description="ID of the chef meal event, if this is a chef meal"
    )
    servings: int = Field(
        ..., 
        description="Number of servings for this meal (e.g., the meal's base or intended portion after cooking)."
    )

class MealPlanSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meals: List[MealPlanMeal]

class MealCompatibility(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_compatible: bool = Field(..., description="True if the meal fits every user preference")
    violations: list[str] = Field(...,
        description="Human-readable list of each preference it violated")
    confidence: float = Field(...,
        description="Model confidence that its judgement is correct, ge=0, le=1")
    
class MealToReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_id: int = Field(..., description="ID of the meal to be replaced")
    day: str = Field(..., description="Day of the week (e.g., 'Monday')")
    meal_type: str = Field(..., description="Type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')")

class MealsToReplaceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meals_to_replace: List[MealToReplace] = Field(..., description="List of meals that need to be replaced")

class MealTypeAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_type: MealType = Field(
        ...,
        description="The type of the meal. Must be one of: Breakfast, Lunch, Dinner."
    )

    example : ClassVar[Dict[str, Any]] = {
        "meal_type": "Breakfast"
    }

class SanitySchema(BaseModel):
    allergen_check: bool = Field(
        ..., 
        description="True if the meal is allergen-free, False if it contains any allergens."
    )

    model_config = ConfigDict(extra="forbid")
    example : ClassVar[Dict[str, Any]] = {
        "allergen_check": True
    }

class RelevantSchema(BaseModel):
    relevant: bool = Field(
        ..., 
        description="True if the question is relevant, False if it it is malicious and/or not related to the service."
    )

    model_config = ConfigDict(extra="forbid")
    example : ClassVar[Dict[str, Any]] = {
        "relevant": True
    }


class DietaryPreferencesSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dietary_preferences: List[DietaryPreference] = Field(
        ..., 
        description="List of dietary preferences applicable to the meal."
    )

    example : ClassVar[Dict[str, Any]] = {
            "dietary_preferences": ["Vegan", "Gluten-Free"]
        }

class DietaryPreferenceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(..., description="A detailed description of the dietary preference.")
    allowed: List[str] = Field(..., description="A list of allowed foods for this dietary preference.")
    excluded: List[str] = Field(..., description="A list of excluded foods for this dietary preference.")

# New Pydantic Models for Pantry Items
class ReplenishItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_name: str = Field(..., description="Name of the item to replenish")
    quantity: int = Field(..., description="Quantity needed to meet the emergency supply goal")
    unit: str = Field(..., description="Unit of measurement (e.g., cans, grams)")

class ReplenishItemsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items_to_replenish: List[ReplenishItem] = Field(..., description="List of items to replenish")

# New Pydantic Models for Approving Meal Plans
class MealItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name: str = Field(..., description="Name of the meal.")
    meal_type: str = Field(..., description="Type of the meal (e.g., Breakfast, Lunch, Dinner).")
    day: str = Field(..., description="Day of the week the meal is planned for.")
    description: str = Field(..., description="A tempting description of the meal.")
    is_chef_meal: bool = Field(
        ...,
        description="Indicates if this meal was created by a chef"
    )
    chef_name: Optional[str] = Field(
        ...,
        description="Name of the chef who created this meal, if applicable"
    )
    chef_meal_event_id: Optional[int] = Field(
        ...,
        description="ID of the chef meal event, if this is a chef meal"
    )

class MealPlanApprovalEmailSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_name: str = Field(..., description="Name of the user.")
    meal_plan_week_start: str = Field(..., description="Start date of the meal plan week.")
    meal_plan_week_end: str = Field(..., description="End date of the meal plan week.")
    meals: List[MealItem] = Field(..., description="The full list of the meals included in the meal plan, ordered by day and meal type.")
    summary_text: str = Field(..., description="A tempting summary of the meal plan designed to entice the user to click the approval link.")

    example : ClassVar[Dict[str, Any]] = {
            "user_name": "JohnDoe",
            "meal_plan_week_start": "2024-10-22",
            "meal_plan_week_end": "2024-10-28",
            "meals": [
                    {
                        "meal_name": "Oatmeal with Fresh Berries",
                        "meal_type": "Breakfast",
                        "day": "Monday",
                        "description": "A warm bowl of hearty oatmeal topped with juicy, fresh berries to start your day off right.",
                        "is_chef_meal": False,
                        "chef_name": None,
                        "chef_meal_event_id": None
                    },
                    {
                        "meal_name": "Grilled Chicken Salad",
                        "meal_type": "Lunch",
                        "day": "Monday",
                        "description": "Tender grilled chicken over a bed of crisp greens with a zesty vinaigrette.",
                        "is_chef_meal": False,
                        "chef_name": None,
                        "chef_meal_event_id": None
                    }
                ],
                "summary_text": "We've put together a week of mouthwatering meals just for you, JohnDoe! Whether you're enjoying a hearty breakfast of Oatmeal with Fresh Berries or a refreshing Grilled Chicken Salad, your week is set to be delicious. Ready to approve your meal plan?"
            }


# Bulk Meal Plan Prepping
class BulkPrepStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_number: int = Field(..., description="Step number in the bulk preparation sequence.")
    meal_type: str = Field(..., description="Type of meal for the step (e.g., Breakfast, Lunch, Dinner).")
    description: str = Field(..., min_length=1, description="Detailed description of the step. Cannot be empty.")
    duration: Optional[str] = Field(..., description="Estimated duration for the step. If not provided, defaults to None.")
    ingredients: Optional[List[str]] = Field(..., description="List of ingredients needed for this step.")
    cooking_temperature: Optional[str] = Field(..., description="Cooking temperature if applicable.")
    cooking_time: Optional[str] = Field(..., description="Cooking time if applicable.")
    notes: Optional[str] = Field(..., description="Additional notes or tips.")

    example : ClassVar[Dict[str, Any]] = {
            "step_number": 1,
            "meal_type": "Lunch",
            "description": "Chop all vegetables and store in airtight containers.",
            "duration": "30 minutes",
            "ingredients": ["bell peppers", "onions", "carrots"],
            "cooking_temperature": "180C",
                "cooking_time": "12 minutes",
                "notes": "Store each vegetable in a separate container to maintain freshness."
            }
        

class DailyTaskStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_number: int = Field(..., description="Step number in the daily task sequence.")
    meal_type: str = Field(..., description="Type of meal for the step (e.g., Breakfast, Lunch, Dinner).")
    description: str = Field(..., min_length=1, description="Detailed description of the step. Cannot be empty.")
    duration: Optional[str] = Field(..., description="Estimated duration for the step. If not provided, defaults to None.")
    ingredients: Optional[List[str]] = Field(..., description="List of ingredients needed for this step.")
    cooking_temperature: Optional[str] = Field(..., description="Cooking temperature if applicable.")
    cooking_time: Optional[str] = Field(..., description="Cooking time if applicable.")
    notes: Optional[str] = Field(..., description="Additional notes or tips.")

    example : ClassVar[Dict[str, Any]] = {
            "step_number": 1,
            "meal_type": "Breakfast",
            "description": "Reheat the pre-cooked quinoa in a microwave for 2 minutes.",
            "duration": "2 minutes",
            "ingredients": ["quinoa"],
                "cooking_temperature": "300W",
                "cooking_time": "2 minutes",
                "notes": "Cover the bowl with a damp paper towel to prevent drying out."
            }
        

class DailyTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_number: int = Field(..., description="Step number in the daily task sequence.")
    day: str = Field(..., description="Day of the week (e.g., 'Monday').")
    tasks: List[DailyTaskStep] = Field(..., description="List of tasks for the day.")
    total_estimated_time: Optional[str] = Field(..., description="Total estimated time to complete all tasks for the day.")

    example : ClassVar[Dict[str, Any]] = {
            "day": "Monday",
            "step_number": 1,
            "tasks": [
                    {
                        "step_number": 1,
                        "meal_type": "Breakfast",
                        "description": "Reheat the marinated grilled chicken in the oven at 350°F for 10 minutes.",
                        "duration": "10 minutes",
                        "ingredients": ["grilled chicken"],
                        "cooking_temperature": "350°F",
                        "cooking_time": "10 minutes",
                        "notes": "Ensure the chicken is heated thoroughly."
                    },
                    {
                        "step_number": 2,
                        "meal_type": "Breakfast",
                        "description": "Assemble the salad with mixed greens, cherry tomatoes, cucumbers, and the reheated chicken.",
                        "duration": "5 minutes",
                        "ingredients": ["mixed greens", "cherry tomatoes", "cucumbers", "reheated chicken"],
                        "notes": "Dress the salad just before serving."
                    }
                ],
                "total_estimated_time": "15 minutes"
            }
        


class BulkPrepInstructions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bulk_prep_steps: List[BulkPrepStep] = Field(..., description="List of steps for bulk preparation.")
    daily_tasks: List[DailyTask] = Field(..., description="List of daily follow-up tasks, each representing a day of the week.")

    example : ClassVar[Dict[str, Any]] = {
            "bulk_prep_steps": [
                {
                        "step_number": 1,
                        "meal_type": "Breakfast",
                        "description": "Wash, hull, and slice 3 cups of strawberries. Store in an airtight container.",
                        "duration": "15 minutes",
                        "ingredients": ["strawberries"],
                        "notes": "Keep refrigerated and use within 3 days."
                    },
                    {
                        "step_number": 2,
                        "meal_type": "Lunch",
                        "description": "Marinate 4 chicken breasts in olive oil, lemon juice, garlic, and herbs. Refrigerate overnight.",
                        "duration": "10 minutes",
                        "ingredients": ["chicken breasts", "olive oil", "lemon juice", "garlic", "herbs"],
                        "notes": "Use a sealed container. Marinate at least 8 hours."
                    },
                    {
                        "step_number": 3,
                        "meal_type": "Dinner",
                        "description": "Peel and chop 2 cups of carrots and 1 cup of onions. Store in separate airtight containers.",
                        "duration": "20 minutes",
                        "ingredients": ["carrots", "onions"],
                        "notes": "Label containers to avoid confusion."
                    }
                ],
                "daily_tasks": [
                    {
                        "day": "Monday",
                        "step_number": 1,
                        "tasks": [
                            {
                                "step_number": 1,
                                "meal_type": "Breakfast",
                                "description": "Reheat the pre-cooked quinoa in the microwave for 2 minutes.",
                                "duration": "2 minutes",
                                "ingredients": ["pre-cooked quinoa"],
                                "cooking_temperature": "300W",
                                "cooking_time": "2 minutes",
                                "notes": "Cover with a damp paper towel to retain moisture."
                            },
                            {
                                "step_number": 2,
                                "meal_type": "Breakfast",
                                "description": "Top quinoa with sliced strawberries and a drizzle of honey.",
                                "duration": "3 minutes",
                                "ingredients": ["sliced strawberries", "honey"],
                                "notes": "Serve immediately."
                            }
                        ],
                        "total_estimated_time": "5 minutes"
                    },
                    {
                        "day": "Tuesday",
                        "step_number": 1,
                        "tasks": [
                            {
                                "step_number": 1,
                                "meal_type": "Lunch",
                                "description": "Grill the marinated chicken breasts over medium heat until fully cooked (internal temp 165°F).",
                                "duration": "15 minutes",
                                "ingredients": ["marinated chicken"],
                                "cooking_temperature": "375°F",
                                "cooking_time": "15 minutes",
                                "notes": "Flip halfway through cooking. Let rest 5 minutes before slicing."
                            },
                            {
                                "step_number": 2,
                                "meal_type": "Lunch",
                                "description": "Assemble a salad with mixed greens, cherry tomatoes, and sliced grilled chicken.",
                                "duration": "5 minutes",
                                "ingredients": ["mixed greens", "cherry tomatoes", "grilled chicken"],
                                "notes": "Dress just before serving."
                            },
                            {
                                "step_number": 3,
                                "meal_type": "Lunch",
                                "description": "Drizzle salad with a light vinaigrette and toss gently.",
                                "duration": "2 minutes",
                                "ingredients": ["vinaigrette"],
                                "notes": "Adjust seasoning to taste."
                            }
                        ],
                        "total_estimated_time": "22 minutes"
                    },
                    {
                        "day": "Wednesday",
                        "step_number": 1,
                        "tasks": [
                            {
                                "step_number": 1,
                                "meal_type": "Dinner",
                                "description": "Sauté chopped carrots and onions in a saucepan with a teaspoon of olive oil until softened.",
                                "duration": "10 minutes",
                                "ingredients": ["chopped carrots", "chopped onions", "olive oil"],
                                "cooking_temperature": "medium",
                                "cooking_time": "10 minutes",
                                "notes": "Stir occasionally to prevent burning."
                            },
                            {
                                "step_number": 2,
                                "meal_type": "Dinner",
                                "description": "Add pre-cooked lentils and vegetable broth to the saucepan and simmer for 5 minutes.",
                                "duration": "5 minutes",
                                "ingredients": ["pre-cooked lentils", "vegetable broth"],
                                "cooking_temperature": "medium-low",
                                "cooking_time": "5 minutes",
                                "notes": "Season with salt and pepper to taste."
                            },
                            {
                                "step_number": 3,
                                "meal_type": "Dinner",
                                "description": "Serve the lentil stew hot, garnished with fresh parsley.",
                                "duration": "2 minutes",
                                "ingredients": ["fresh parsley"],
                                "notes": "Serve immediately for best flavor."
                            }
                        ],
                        "total_estimated_time": "17 minutes"
                    }
                ]
            }

# Pantry Management
class PantryTagsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: List[str] = Field(
        ...,
        description="A list of tags describing the pantry item."
    )

class UsageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_name: str = Field(..., description="Exact name of the pantry item to use.")
    quantity_used: float = Field(..., description="How many units the recipe calls for.")
    unit: str = Field(..., description="Unit of measure, e.g. 'cups', 'pieces', 'grams'")

class UsageList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """
    A top-level object containing an array of usage items. 
    This structure satisfies OpenAI's JSON Schema requirement 
    that the top-level is 'type: object'.
    """
    usage_items: List[UsageItem] = Field(
        ...,
        description="An array of items indicating how much of each pantry item to use."
    )

    example : ClassVar[Dict[str, Any]] = {
            "usage_items": [
                {
                            "item_name": "milk",
                            "quantity_used": 2.0,
                            "unit": "cups"
                        },
                        {
                            "item_name": "eggs",
                            "quantity_used": 3,
                            "unit": "pieces"
                }
            ]
        }

#Ingredients Schema
class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_name: str = Field(..., description="Exact name of the pantry item to use.")
    quantity_used: float = Field(..., description="How many units the recipe calls for.")
    unit: str = Field(..., description="Unit of measure, e.g. 'cups', 'pieces', 'grams'")
    notes: Optional[str] = Field(..., description="Any special notes about the ingredient.")

# YouTube Video Ranking Models
class VideoRankingItem(BaseModel):
    """Individual video ranking information."""
    model_config = ConfigDict(extra="forbid")
    
    video_id: str = Field(..., description="YouTube video ID")
    relevance_score: float = Field(..., description="Relevance score (0-10)")
    relevance_explanation: str = Field(..., description="Explanation of why the video is relevant")
    matching_ingredients: List[str] = Field(
        ...,
        description="List of ingredients mentioned in the video that match the meal"
    )
    matching_techniques: List[str] = Field(
        ...,
        description="List of cooking techniques mentioned in the video that match the meal"
    )
    recommended: bool = Field(
        ..., 
        description="Whether this video is recommended for the meal"
    )

class VideoRankings(BaseModel):
    """Top-level container for video rankings."""
    model_config = ConfigDict(extra="forbid")
    
    ranked_videos: List[VideoRankingItem] = Field(
        ...,
        description="List of videos ranked by relevance to the meal"
    )

# -------------------------------------------------
# Atomic meal-plan change – structured-output schema
# -------------------------------------------------
class MealSlotDirective(BaseModel):
    """Instruction set for ONE MealPlanMeal row."""
    model_config = ConfigDict(extra="forbid")
    meal_plan_meal_id: int = Field(..., description="PK of MealPlanMeal to examine")
    meal_name: str = Field(..., description="Human-readable meal name")
    change_rules: List[str] = Field(
        ...,
        description=(
            "List of directives for this slot – e.g. "
            "'vegan', 'no rice', 'specific:pancakes'. "
            "Empty array ⇒ leave slot untouched."
        ),
    )
    should_remove: Optional[bool] = Field(
        ..., 
        description=(
            "Whether to delete this meal entirely and not replace it. "
            "NOTE: must not check for a value of False – it might be missing "
            "in the original request. Check for *truthiness* instead."
        )
    )
class MealSlotDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_plan_meal_id: int
    meal_name: str
    change_rules: List[str]

    should_remove: Optional[bool] = Field(..., description="True if the slot should be deleted outright.")

    # ②  back-fill the default in a model-level validator
    @model_validator(mode="before")
    def set_default_should_remove(cls, data):
        data.setdefault("should_remove", False)
        return data
    
class MealPlanModificationRequest(BaseModel):
    """Top-level structured output expected from the parser Assistant."""
    model_config = ConfigDict(extra="forbid")
    slots: List[MealSlotDirective]

# --- User-prompt → slot map ---------------------------------
class PromptedSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: str = Field(..., description="^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$")
    meal_type: MealType  # reuse existing Enum
    notes: Optional[str] = Field(
        ..., description="Optional extra info extracted from the prompt."
    )

class PromptMealMap(BaseModel):
    """
    Parsed intent extracted from a free-text user prompt.
    """
    model_config = ConfigDict(extra="forbid")

    user_prompt: str
    slots: List[PromptedSlot] = Field(..., description="List of meal slots to plan")

# Payment processing
class PaymentInfoSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkout_url: str = Field(..., description="Checkout URL")
    session_id: str = Field(..., description="Stripe session ID")
    html_button: str = Field(..., description="HTML button containing the full checkout url")

# --- Ingredient Substitution Schemas ----------------------------------------

class IngredientSubstitution(BaseModel):
    """A single ingredient and its safe alternatives."""
    model_config = ConfigDict(extra="forbid")
    ingredient: str = Field(..., description="Name of the flagged ingredient")
    alternatives: List[str] = Field(
        ..., description="Array of safe substitution suggestions for the ingredient"
    )


class IngredientSubstitutions(BaseModel):
    """Schema containing a list of substitution recommendations."""

    model_config = ConfigDict(extra="forbid")

    substitutions: List[IngredientSubstitution] = Field(
        ..., description="List of substitution recommendations"
    )

    example: ClassVar[Dict[str, Any]] = {
        "substitutions": [
            {
                "ingredient": "milk",
                "alternatives": ["almond milk", "coconut milk", "soy milk"],
            },
            {
                "ingredient": "peanut butter",
                "alternatives": ["sunflower seed butter", "almond butter"],
            },
            {
                "ingredient": "wheat flour",
                "alternatives": ["oat flour", "rice flour"],
            },
        ]
    }

# --- Meal Modification Schemas ----------------------------------------------

class IngredientChange(BaseModel):
    """
    Represents a single ingredient substitution pair.
    """
    model_config = ConfigDict(extra="forbid")

    original: str = Field(..., description="Original ingredient name that needs substitution")
    substitute: str = Field(..., description="Chosen substitute ingredient name")


class ModifiedMealSchema(BaseModel):
    """
    Schema describing a meal that has been adapted with ingredient substitutions.
    """
    model_config = ConfigDict(extra="forbid")

    modified_name: str = Field(..., description="New name of the adapted meal")
    modified_description: str = Field(..., description="Updated description of the adapted meal")
    modified_instructions: str = Field(..., description="Full cooking instructions incorporating substitutions")
    ingredient_changes: List[IngredientChange] = Field(
        ..., description="List of ingredient substitution mappings"
    )

    example: ClassVar[Dict[str, Any]] = {
        "modified_name": "Gluten‑Free Pancakes",
        "modified_description": (
            "Fluffy pancakes adapted to be gluten‑free by replacing wheat flour with oat flour."
        ),
        "modified_instructions": (
            "Combine oat flour, baking powder, milk, and eggs. Cook on a greased skillet "
            "over medium heat until bubbles form and edges are set, then flip and finish."
        ),
        "ingredient_changes": [
            {"original": "wheat flour", "substitute": "oat flour"}
        ],
    }