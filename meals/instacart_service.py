"""
Helper function to create an Instacart shopping list from the application's shopping list data.

This module provides functionality to transform the application's shopping list data
into the Instacart API payload format and generate a shopping cart link.
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from django.conf import settings
from utils.redis_client import get, set, delete
from meals.pydantic_models import Ingredient
from openai import OpenAI
from django.conf import settings
import traceback
from shared.utils import get_openai_client

logger = logging.getLogger(__name__)



def normalize_lines(lines: list[str]) -> dict:
    prompt = "Turn these loose shopping-list lines into structured JSON ensuring the items are actual shopping list items.\n---\n" + "\n".join(lines)
    r = get_openai_client().responses.create(
        model="gpt-4.1-nano",
        input=[{"role": "user", "content": prompt}],
        text={
            "format": {
                'type': 'json_schema',
                'name': 'normalized_ingredient_list',
                'schema': Ingredient.model_json_schema()
            }
        }
    )
    # GPT‑4.1‑nano returns JSON‑text; convert to dict
    return json.loads(r.output_text)


# Don't initialize the API key at module level to avoid issues if settings aren't loaded yet
# We'll get it from settings when needed
# Unit mapping from application units to Instacart-supported units
UNIT_MAPPING = {
    # Weight units
    "g": "gram",
    "gram": "gram",
    "grams": "gram",
    "kg": "kilogram",
    "kilogram": "kilogram",
    "kilograms": "kilogram",
    "oz": "ounce",
    "ounce": "ounce",
    "ounces": "ounce",
    "lb": "pound",
    "lbs": "pound",
    "pound": "pound",
    "pounds": "pound",
    
    # Volume units
    "ml": "milliliter",
    "milliliter": "milliliter",
    "milliliters": "milliliter",
    "l": "liter",
    "liter": "liter",
    "liters": "liter",
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "tbsp": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "cup": "cup",
    "cups": "cup",
    "pint": "pint",
    "pints": "pint",
    "quart": "quart",
    "quarts": "quart",
    "gallon": "gallon",
    "gallons": "gallon",
    "fl oz": "fluid_ounce",
    "fluid ounce": "fluid_ounce",
    "fluid ounces": "fluid_ounce",
    
    # Count units
    "each": "each",
    "count": "each",
    "piece": "each",
    "pieces": "each",
    
    # Package units
    "package": "package",
    "packages": "package",
    "box": "package",
    "boxes": "package",
    "can": "package",
    "cans": "package",
    "jar": "package",
    "jars": "package",
    "bottle": "package",
    "bottles": "package",
}

def create_instacart_shopping_list(
    shopping_list_data: dict,
    user_id: int = None,
    meal_plan_id: int = None,
    api_key: str = None,
    cache_duration_days: int = 30,
    app_name: str = "sautAI",
    postal_code: str = None
) -> dict:
    """
    Creates an Instacart shopping list from the application's shopping list data and returns the link.
    
    Args:
        shopping_list_data: Dictionary containing shopping list data (conforming to ShoppingListSchema)
        user_id: Optional user ID for caching purposes
        meal_plan_id: Optional meal plan ID for caching purposes
        api_key: Instacart API key (if None, will use the one from settings)
        cache_duration_days: Number of days until the link expires (max 365)
        app_name: Name of the application to use in the title
        postal_code: User's postal code for location-based store selection (for US and Canada)
        
    Returns:
        Dictionary with keys:
        - status: 'success' or 'error'
        - instacart_url: URL to the Instacart shopping list (if successful)
        - message: Success or error message
    """
    try:
        # 1. Check cache if user_id and meal_plan_id are provided
        if user_id and meal_plan_id:
            cache_key = f"instacart_link_{user_id}_{meal_plan_id}"
            cached_url = get(cache_key)
            if cached_url:
                logger.info(f"Using cached Instacart URL for user {user_id}, meal plan {meal_plan_id}")
                return {
                    "status": "success",
                    "instacart_url": cached_url,
                    "message": "Retrieved cached Instacart shopping list URL"
                }
        
        # 2. Validate shopping list data
        if not shopping_list_data:
            return {
                "status": "error",
                "message": "Shopping list data is empty or invalid"
            }
        
        # 3. Get API key
        if not api_key:
            api_key = os.getenv('INSTACART_API_KEY')
            if not api_key:
                logger.error("Instacart API key not provided and not found in settings")
                return {
                    "status": "error",
                    "message": "Instacart API key not provided and not found in settings"
                }
            else:
                logger.debug("Using Instacart API key from settings")
        
        # 4. Transform shopping list data to Instacart payload
        instacart_payload = _transform_to_instacart_payload(
            shopping_list_data, 
            cache_duration_days, 
            app_name,
            postal_code
        )
        # 5. Call Instacart API
        instacart_url = _call_instacart_api(instacart_payload, api_key)
        
        # 6. Cache the URL if user_id and meal_plan_id are provided
        if user_id and meal_plan_id and instacart_url:
            cache_key = f"instacart_link_{user_id}_{meal_plan_id}"
            set(cache_key, instacart_url, timeout=cache_duration_days * 86400)  # Convert days to seconds
        
        return {
            "status": "success",
            "instacart_url": instacart_url,
            "message": "Successfully created Instacart shopping list"
        }
        
    except Exception as e:
        logger.error(f"Error creating Instacart shopping list: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create Instacart shopping list: {str(e)}"
        }

def _transform_to_instacart_payload(
    shopping_list_data: dict, 
    cache_duration_days: int, 
    app_name: str,
    postal_code: str = None
) -> dict:
    """
    Transforms the application's shopping list data into the Instacart API payload format.
    
    Args:
        shopping_list_data: Dictionary containing shopping list data
        cache_duration_days: Number of days until the link expires
        app_name: Name of the application to use in the title
        postal_code: User's postal code for location-based store selection
        
    Returns:
        Dictionary in the Instacart API payload format
    """
    # --- NEW: normalise loose string lines with GPT‑4.1‑nano ----------------
    # If items are plain strings instead of structured dicts, clean them up
    items = shopping_list_data.get('items')
    if items and isinstance(items, list) and items and isinstance(items[0], str):
        try:
            shopping_list_data = normalize_lines(items)
            print("[transform] Normalized items preview:", shopping_list_data.get('items', [])[:5])
        except Exception as e:
            logger.warning(f"normalize_lines failed; continuing with raw items: {e}")
    # ------------------------------------------------------------------------
    # Extract title from shopping list data or use default
    title = shopping_list_data.get('title', f"{app_name} Shopping List")
    
    # Initialize line items array
    line_items = []
    
    # Process each item in the shopping list
    for item in shopping_list_data.get('items', []):
        item_name = item.get('ingredient', '')
        if not item_name:
            continue  # Skip items without a name
        
        # Extract quantity and unit
        quantity = item.get('quantity', '1')
        # Convert quantity to float if it's a string representing a number
        try:
            quantity = float(quantity)
        except (ValueError, TypeError):
            quantity = 1.0
            
        unit = item.get('unit', 'each').lower()
        
        # Map unit to Instacart-supported unit
        instacart_unit = UNIT_MAPPING.get(unit, 'each')
        
        # Create line item
        line_item = {
            "name": item_name,
            "quantity": quantity,
            "unit": instacart_unit
        }
        

        
        line_items.append(line_item)
    
    # Create the payload
    payload = {
        "title": title,
        "link_type": "shopping_list",
        "image_url": "https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg",
        "expires_in": min(cache_duration_days, 365),  # Ensure within Instacart's max limit
        "line_items": line_items
    }
    
    # Add postal code if provided
    if postal_code:
        payload["postal_code"] = postal_code
    
    return payload

def _append_instacart_utm_params(url: str) -> str:
    """
    Append required UTM parameters to Instacart URLs for affiliate tracking.
    
    Args:
        url: The original Instacart URL
        
    Returns:
        URL with UTM parameters appended
    """
    utm_params = "utm_campaign=instacart-idp&utm_medium=affiliate&utm_source=instacart_idp&utm_term=partnertype-mediapartner&utm_content=campaignid-20313_partnerid-6356307"
    
    # Check if URL already has query parameters
    if "?" in url:
        # URL already has query parameters, append with &
        return f"{url}&{utm_params}"
    else:
        # URL doesn't have query parameters, append with ?
        return f"{url}?{utm_params}"

def _call_instacart_api(payload: dict, api_key: str) -> str:
    """
    Calls the Instacart API to create a shopping list and returns the URL.
    
    Args:
        payload: Dictionary in the Instacart API payload format
        api_key: Instacart API key
        
    Returns:
        URL to the Instacart shopping list
        
    Raises:
        Exception: If the API call fails
    """
    # Determine API endpoint
    api_base_url = os.getenv('INSTACART_API_BASE_URL', 'https://connect.instacart.com')
    api_endpoint = f"{api_base_url}/idp/v1/products/products_link"
    
    # Log API request (without the key)
    logger.debug(f"Calling Instacart API at {api_endpoint} with payload: {payload}")
    
    # Set up headers - Instacart requires 'Bearer' prefix for the token
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    # Log that we're using an API key (without showing the actual key)
    logger.debug("Using Instacart API key in Authorization header")
    
    # Make the API call
    response = requests.post(
        api_endpoint,
        data=json.dumps(payload),
        headers=headers,
        timeout=30  # 30-second timeout
    )
    
    # Check for errors
    response.raise_for_status()
    
    # Parse the response
    response_data = response.json()
    
    # Extract and return the URL
    instacart_url = response_data.get('products_link_url')
    if not instacart_url:
        raise ValueError("Instacart API response did not contain a products_link_url")
    
    return _append_instacart_utm_params(instacart_url)

def generate_instacart_link(user_id: int, meal_plan_id: int, postal_code: str = None) -> dict:
    """
    Generate an Instacart shopping list link for a meal plan.
    
    This function:
    1. Checks if the meal plan already has an Instacart URL
    2. If not, retrieves the shopping list for the given meal plan
    3. Transforms it into Instacart format
    4. Calls the Instacart API to generate a shopping link
    5. Saves the generated URL to the meal plan for future use
    
    Args:
        user_id: The user ID
        meal_plan_id: The meal plan ID
        postal_code: The user's postal code for location-based store selection (optional)
        
    Returns:
        Dictionary with keys:
        - status: 'success' or 'error'
        - instacart_url: URL to the Instacart shopping list (if successful)
        - message: Success or error message
        - from_cache: Boolean indicating if the URL was retrieved from the database
    """
    from django.shortcuts import get_object_or_404
    from custom_auth.models import CustomUser, Address
    from meals.models import MealPlan, ShoppingList
    
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the meal plan
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        
        # Precompute whether the meal plan contains chef-created meals
        has_chef_meals = meal_plan.meal.filter(chef__isnull=False).exists()

        # Check if meal plan already has an Instacart URL saved
        if meal_plan.instacart_url:
            logger.info(f"Using existing Instacart URL for meal plan {meal_plan_id}")
            return {
                "status": "success",
                "instacart_url": meal_plan.instacart_url,
                "message": "Retrieved existing Instacart shopping list URL",
                "from_cache": True,
                "has_chef_meals": has_chef_meals
            }
        
        # Use the provided postal code or try to get it from the user's address if not provided
        if not postal_code:
            try:
                # The postal code is stored in the Address model which has a one-to-one relationship with CustomUser
                if hasattr(user, 'address'):
                    postal_code = user.address.input_postalcode
                    if postal_code:
                        logger.info(f"Using postal code {postal_code} from user's address for Instacart")
                    else:
                        logger.warning(f"User {user_id} has an address but no postal code. Location-based store selection will not be available.")
                else:
                    logger.warning(f"User {user_id} has no address. Location-based store selection will not be available.")
            except Exception as e:
                logger.warning(f"Error retrieving postal code for user {user_id}: {str(e)}. Location-based store selection will not be available.")
        
        # Get the shopping list
        shopping_list = ShoppingList.objects.filter(meal_plan=meal_plan).first()
        
        if not shopping_list:
            # If no shopping list exists, generate one
            from meals.pantry_management_tools import generate_shopping_list
            shopping_list_data = generate_shopping_list(user_id, meal_plan_id)
        else:
            # Parse the existing shopping list
            shopping_list_data = json.loads(shopping_list.items)
        
        # Filter out items belonging to chef-created meals
        try:
            if has_chef_meals:
                # Pull chef meal names via DB for efficiency
                chef_meal_names = set(
                    meal_plan.meal.filter(chef__isnull=False).values_list('name', flat=True)
                )
                items = shopping_list_data.get('items') or []
                original_count = len(items)
                if chef_meal_names and original_count:
                    filtered_items = [
                        it for it in items
                        if not any(name in chef_meal_names for name in (it or {}).get('meal_names', []))
                    ]
                    removed_count = original_count - len(filtered_items)
                    if removed_count > 0:
                        logger.info(
                            f"Excluded {removed_count} shopping list item(s) tied to chef-created meals from Instacart payload"
                        )
                    shopping_list_data['items'] = filtered_items
        except Exception as _filter_err:
            logger.warning(f"Failed to filter chef-created meal items for Instacart: {_filter_err}")

        # If everything was filtered out, avoid calling Instacart API with empty items
        if not (shopping_list_data.get('items') or []):
            return {
                "status": "error",
                "message": "No eligible grocery items to send to Instacart after excluding chef-created meals."
            }
        
        # Get the API key from settings
        api_key = os.getenv('INSTACART_API_KEY')
        if not api_key:
            logger.error("Instacart API key not found in environment variables")
            return {
                "status": "error",
                "message": "Having issues connecting to Instacart"
            }
        # Create the Instacart shopping list
        result = create_instacart_shopping_list(
            shopping_list_data=shopping_list_data,
            user_id=user_id,
            meal_plan_id=meal_plan_id,
            api_key=api_key,
            postal_code=postal_code
        )
        
        # If successful, save the URL to the meal plan
        if result.get('status') == 'success' and result.get('instacart_url'):
            meal_plan.instacart_url = result['instacart_url']
            meal_plan.save(update_fields=['instacart_url'])
            result['from_cache'] = False
            logger.info(f"Saved Instacart URL to meal plan {meal_plan_id}")
        
        # Always include presence flag for chef meals
        try:
            result['has_chef_meals'] = has_chef_meals
        except Exception:
            pass
        
        return result
    except Exception as e:
        logger.error(f"Error generating Instacart link: {str(e)}")
        n8n_traceback = {
            'error': str(e),
            'source': 'instacart_service',
            'traceback': f"{traceback.format_exc()}"
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        return {
            "status": "error",
            "message": f"Failed to generate Instacart link: {str(e)}"
        } 