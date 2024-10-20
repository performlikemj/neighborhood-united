# meals/pydantic_models.py
from pydantic import BaseModel, Field, RootModel
from typing import List, Optional, Dict
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

# Define the possible meal types
class MealType(str, Enum):
    BREAKFAST = "Breakfast"
    LUNCH = "Lunch"
    DINNER = "Dinner"

class ShoppingListItem(BaseModel):
    meal_name: Optional[str] = None
    ingredient: str
    quantity: str
    unit: str
    notes: Optional[str] = None
    category: ShoppingCategory = Field(default=ShoppingCategory.MISC) 

class ShoppingList(BaseModel):
    items: List[ShoppingListItem]

class InstructionStep(BaseModel):
    step_number: int
    description: str
    duration: Optional[str] = None

class Instructions(BaseModel):
    steps: List[InstructionStep]

class MealData(BaseModel):
    name: str
    description: str
    dietary_preference: DietaryPreference = Field(default=DietaryPreference.EVERYTHING)
    meal_type: Optional[MealType] = None

class MealOutputSchema(BaseModel):
    meal: MealData
    status: str
    message: str
    current_time: str

class MealPlanMeal(BaseModel):
    day: str  # e.g., "Monday"
    meal_type: str  # e.g., "Breakfast"
    meal_name: str
    meal_description: Optional[str] = None

class MealPlanSchema(BaseModel):
    meals: List[MealPlanMeal]

class MealToReplace(BaseModel):
    meal_id: int = Field(..., description="ID of the meal to be replaced")
    day: str = Field(..., description="Day of the week (e.g., 'Monday')")
    meal_type: str = Field(..., description="Type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')")

class MealsToReplaceSchema(BaseModel):
    meals_to_replace: List[MealToReplace] = Field(..., description="List of meals that need to be replaced")

class MealTypeAssignment(BaseModel):
    meal_type: MealType = Field(
        ...,
        description="The type of the meal. Must be one of: Breakfast, Lunch, Dinner."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "meal_type": "Breakfast"
            }
        }
    }

class SanitySchema(BaseModel):
    allergen_check: bool = Field(
        ..., 
        description="True if the meal is allergen-free, False if it contains any allergens."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "allergen_check": True
            }
        }
    }

class RelevantSchema(BaseModel):
    relevant: bool = Field(
        ..., 
        description="True if the question is relevant, False if it it is malicious and/or not related to the service."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "relevant": True
            }
        }
    }


class DietaryPreferencesSchema(BaseModel):
    dietary_preferences: List[DietaryPreference] = Field(
        ..., 
        description="List of dietary preferences applicable to the meal."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "dietary_preferences": ["Vegan", "Gluten-Free"]
            }
        }

class DietaryPreferenceDetail(BaseModel):
    description: str = Field(..., description="A detailed description of the dietary preference.")
    allowed: List[str] = Field(..., description="A list of allowed foods for this dietary preference.")
    excluded: List[str] = Field(..., description="A list of excluded foods for this dietary preference.")

# New Pydantic Models for Pantry Items
class ReplenishItem(BaseModel):
    item_name: str = Field(..., description="Name of the item to replenish")
    quantity: int = Field(..., description="Quantity needed to meet the emergency supply goal")
    unit: str = Field(..., description="Unit of measurement (e.g., cans, grams)")

class ReplenishItemsSchema(BaseModel):
    items_to_replenish: List[ReplenishItem] = Field(..., description="List of items to replenish")
