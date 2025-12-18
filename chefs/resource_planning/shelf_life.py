"""
Shelf Life Determination Service

Uses Groq LLM to determine ingredient shelf life and storage recommendations.
Results are cached in the database to avoid repeated API calls.
"""
import json
import logging
import os
from typing import List, Optional
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from pydantic import BaseModel, Field
from typing import Literal

logger = logging.getLogger(__name__)


# Pydantic schemas for structured output
class IngredientShelfLife(BaseModel):
    """Shelf life information for a single ingredient."""
    ingredient_name: str = Field(..., description="Name of the ingredient")
    shelf_life_days: int = Field(..., description="Estimated shelf life in days under recommended storage")
    storage_type: Literal['refrigerated', 'frozen', 'pantry', 'counter'] = Field(
        ...,
        description="Recommended storage method"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional storage tips or considerations"
    )


class ShelfLifeResponse(BaseModel):
    """Response containing shelf life info for multiple ingredients."""
    ingredients: List[IngredientShelfLife]


def _get_groq_client():
    """Lazy Groq client factory - same pattern as other services."""
    try:
        from groq import Groq
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key:
            return Groq(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to create Groq client: {e}")
    return None


def get_ingredient_shelf_lives(
    ingredient_names: List[str],
    storage_preference: Optional[str] = None
) -> ShelfLifeResponse:
    """
    Determine shelf life for a batch of ingredients using Groq.
    
    Args:
        ingredient_names: List of ingredient names to analyze
        storage_preference: Optional storage preference hint ('refrigerated', 'frozen', 'pantry', 'counter')
        
    Returns:
        ShelfLifeResponse with shelf life info for each ingredient
        
    Raises:
        ValueError: If Groq client is unavailable or API call fails
    """
    if not ingredient_names:
        return ShelfLifeResponse(ingredients=[])
    
    groq_client = _get_groq_client()
    if not groq_client:
        raise ValueError("Groq client not available - GROQ_API_KEY must be set")
    
    # Build the prompt
    ingredients_list = "\n".join([f"- {name}" for name in ingredient_names])
    
    storage_hint = ""
    if storage_preference:
        storage_hint = f"\nPreferred storage method if applicable: {storage_preference}"
    
    system_prompt = """You are a food safety expert. Determine the shelf life for each ingredient.

For each ingredient, provide:
1. shelf_life_days: How many days the ingredient stays fresh under recommended storage (be conservative for food safety)
2. storage_type: The recommended storage method:
   - "refrigerated": Items needing 35-40°F (most produce, dairy, meat)
   - "frozen": Items that should/can be frozen for extended life
   - "pantry": Dry goods, canned items, shelf-stable products
   - "counter": Items that shouldn't be refrigerated (bananas, tomatoes, etc.)
3. notes: Any important storage tips (optional)

Guidelines:
- For fresh produce: typically 3-7 days refrigerated
- For fresh meat/poultry: 2-4 days refrigerated
- For fresh fish: 1-2 days refrigerated
- For dairy: check typical expiration windows
- For pantry items: consider opened vs unopened
- Always err on the side of food safety

Return ONLY valid JSON matching the schema."""

    user_prompt = f"""Determine shelf life for these ingredients:
{ingredients_list}
{storage_hint}

Return JSON with an "ingredients" array containing shelf life info for each ingredient."""

    try:
        response = groq_client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            top_p=1,
            stream=False,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "shelf_life_response",
                    "schema": ShelfLifeResponse.model_json_schema(),
                },
            },
        )
        
        raw_json = response.choices[0].message.content or "{}"
        result = ShelfLifeResponse.model_validate_json(raw_json)
        
        logger.info(f"Successfully determined shelf life for {len(result.ingredients)} ingredients")
        return result
        
    except Exception as e:
        logger.error(f"Error determining shelf life: {e}")
        raise ValueError(f"Failed to determine shelf life: {e}")


def update_recipe_ingredient_shelf_life(recipe_ingredient) -> bool:
    """
    Update shelf life data for a single RecipeIngredient.
    
    Args:
        recipe_ingredient: RecipeIngredient model instance
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        response = get_ingredient_shelf_lives([recipe_ingredient.name])
        
        if response.ingredients:
            shelf_info = response.ingredients[0]
            recipe_ingredient.shelf_life_days = shelf_info.shelf_life_days
            recipe_ingredient.storage_type = shelf_info.storage_type
            recipe_ingredient.shelf_life_updated_at = timezone.now()
            recipe_ingredient.save(update_fields=[
                'shelf_life_days',
                'storage_type',
                'shelf_life_updated_at'
            ])
            return True
            
    except Exception as e:
        logger.error(f"Failed to update shelf life for {recipe_ingredient.name}: {e}")
    
    return False


def batch_update_shelf_lives(recipe_ingredients, batch_size: int = 20) -> dict:
    """
    Batch update shelf life for multiple RecipeIngredients.
    
    Groups ingredients and makes efficient API calls.
    
    Args:
        recipe_ingredients: QuerySet or list of RecipeIngredient instances
        batch_size: Number of ingredients per API call (default 20)
        
    Returns:
        Dict with 'updated' count and 'failed' list
    """
    from chefs.resource_planning.models import RecipeIngredient
    
    # Group by unique ingredient name to avoid duplicate API calls
    ingredients_by_name = {}
    for ri in recipe_ingredients:
        if ri.name not in ingredients_by_name:
            ingredients_by_name[ri.name] = []
        ingredients_by_name[ri.name].append(ri)
    
    unique_names = list(ingredients_by_name.keys())
    updated = 0
    failed = []
    
    # Process in batches
    for i in range(0, len(unique_names), batch_size):
        batch_names = unique_names[i:i + batch_size]
        
        try:
            response = get_ingredient_shelf_lives(batch_names)
            
            # Create lookup by name (case-insensitive)
            shelf_life_map = {
                info.ingredient_name.lower(): info
                for info in response.ingredients
            }
            
            # Update all matching RecipeIngredients
            now = timezone.now()
            for name in batch_names:
                shelf_info = shelf_life_map.get(name.lower())
                
                if shelf_info:
                    for ri in ingredients_by_name[name]:
                        ri.shelf_life_days = shelf_info.shelf_life_days
                        ri.storage_type = shelf_info.storage_type
                        ri.shelf_life_updated_at = now
                        ri.save(update_fields=[
                            'shelf_life_days',
                            'storage_type',
                            'shelf_life_updated_at'
                        ])
                        updated += 1
                else:
                    failed.extend([ri.id for ri in ingredients_by_name[name]])
                    
        except Exception as e:
            logger.error(f"Batch shelf life update failed: {e}")
            for name in batch_names:
                failed.extend([ri.id for ri in ingredients_by_name[name]])
    
    return {
        'updated': updated,
        'failed': failed
    }


def get_default_shelf_life(ingredient_name: str) -> dict:
    """
    Fallback shelf life estimation based on ingredient category keywords.
    
    Used when Groq API is unavailable.
    
    Args:
        ingredient_name: Name of the ingredient
        
    Returns:
        Dict with shelf_life_days and storage_type
    """
    name_lower = ingredient_name.lower()
    
    # Fresh meat/poultry
    if any(word in name_lower for word in ['chicken', 'beef', 'pork', 'turkey', 'lamb', 'ground']):
        return {'shelf_life_days': 3, 'storage_type': 'refrigerated'}
    
    # Fresh fish/seafood
    if any(word in name_lower for word in ['fish', 'salmon', 'shrimp', 'tuna', 'cod', 'tilapia', 'seafood']):
        return {'shelf_life_days': 2, 'storage_type': 'refrigerated'}
    
    # Dairy
    if any(word in name_lower for word in ['milk', 'cream', 'yogurt', 'cheese', 'butter']):
        return {'shelf_life_days': 7, 'storage_type': 'refrigerated'}
    
    # Eggs
    if 'egg' in name_lower:
        return {'shelf_life_days': 21, 'storage_type': 'refrigerated'}
    
    # Leafy greens
    if any(word in name_lower for word in ['lettuce', 'spinach', 'kale', 'arugula', 'greens', 'salad']):
        return {'shelf_life_days': 5, 'storage_type': 'refrigerated'}
    
    # Fresh herbs
    if any(word in name_lower for word in ['basil', 'cilantro', 'parsley', 'mint', 'dill', 'chive']):
        return {'shelf_life_days': 7, 'storage_type': 'refrigerated'}
    
    # Root vegetables
    if any(word in name_lower for word in ['potato', 'onion', 'garlic', 'carrot', 'beet']):
        return {'shelf_life_days': 14, 'storage_type': 'pantry'}
    
    # Counter fruits
    if any(word in name_lower for word in ['banana', 'tomato', 'avocado', 'mango', 'peach']):
        return {'shelf_life_days': 5, 'storage_type': 'counter'}
    
    # Other fresh produce
    if any(word in name_lower for word in ['pepper', 'cucumber', 'zucchini', 'broccoli', 'cauliflower']):
        return {'shelf_life_days': 7, 'storage_type': 'refrigerated'}
    
    # Grains and pasta
    if any(word in name_lower for word in ['rice', 'pasta', 'flour', 'oats', 'quinoa', 'bread']):
        return {'shelf_life_days': 180, 'storage_type': 'pantry'}
    
    # Canned goods
    if any(word in name_lower for word in ['canned', 'can of', 'beans', 'tomato sauce', 'broth', 'stock']):
        return {'shelf_life_days': 365, 'storage_type': 'pantry'}
    
    # Spices and dried herbs
    if any(word in name_lower for word in ['spice', 'dried', 'cumin', 'paprika', 'oregano', 'thyme']):
        return {'shelf_life_days': 365, 'storage_type': 'pantry'}
    
    # Oils and vinegars
    if any(word in name_lower for word in ['oil', 'vinegar', 'olive', 'vegetable', 'sesame']):
        return {'shelf_life_days': 180, 'storage_type': 'pantry'}
    
    # Condiments
    if any(word in name_lower for word in ['sauce', 'ketchup', 'mustard', 'mayo', 'soy sauce']):
        return {'shelf_life_days': 90, 'storage_type': 'refrigerated'}
    
    # Frozen items
    if 'frozen' in name_lower:
        return {'shelf_life_days': 90, 'storage_type': 'frozen'}
    
    # Default: assume refrigerated with moderate shelf life
    return {'shelf_life_days': 5, 'storage_type': 'refrigerated'}






