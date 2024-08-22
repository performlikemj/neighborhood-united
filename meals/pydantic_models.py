# meals/pydantic_models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

class ShoppingListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal_name: Optional[str] = None
    ingredient: str
    quantity: str
    unit: str
    notes: Optional[str] = None

class ShoppingList(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: List[ShoppingListItem]

class InstructionStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step_number: int
    description: str
    duration: Optional[str] = None

class Instructions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    steps: List[InstructionStep]

class MealData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    dietary_preference: Optional[str] = None

class MealOutputSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal: MealData
    status: str
    message: str
    current_time: str