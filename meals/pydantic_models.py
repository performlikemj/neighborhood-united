# meals/pydantic_models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ShoppingListItem(BaseModel):
    meal_name: Optional[str] = None
    ingredient: str
    quantity: str
    unit: str
    notes: Optional[str] = None

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
    dietary_preference: Optional[str] = None

class MealOutputSchema(BaseModel):
    meal: MealData
    status: str
    message: str
    current_time: str