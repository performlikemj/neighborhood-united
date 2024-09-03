# meals/pydantic_models.py
from pydantic import BaseModel, Field
from typing import List, Optional
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
    dietary_preference: Optional[DietaryPreference] = None

class MealOutputSchema(BaseModel):
    meal: MealData
    status: str
    message: str
    current_time: str