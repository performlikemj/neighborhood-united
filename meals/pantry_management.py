"""
Focus: Pantry item handling, replenishment, and emergency supply logic.
"""
import json
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from pydantic import ValidationError
from celery import shared_task
from custom_auth.models import CustomUser
from shared.utils import generate_user_context, get_openai_client
from meals.models import PantryItem, Tag, MealPlanMealPantryUsage
from meals.pydantic_models import ReplenishItemsSchema, PantryTagsSchema
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

def get_user_pantry_items(user):
    """
    Retrieve a list of pantry items for a user.
    """
    pantry_items = user.pantry_items.all()
    return [item.item_name.lower() for item in pantry_items]

def check_item_for_allergies_gpt(item_name: str, user) -> bool:
    """
    Returns True if safe (no potential allergens), False if unsafe.
    """
    user_allergies = set((user.allergies or []) + (user.custom_allergies or []))
    allergies_str = ', '.join(user_allergies) if user_allergies else 'None'
    user_context = generate_user_context(user)

    # The prompt ensures GPT focuses on allergen presence
    prompt_messages = [
        {
            "role": "developer",
            "content": (
                """
                Check whether a pantry item could contain any potential allergens listed by the user and return a boolean response indicating its safety.

                Use the following schema to communicate results.

                # Steps

                1. **Input Understanding**: 
                - Receive a description of a pantry item and a list of potential allergens from the user.
                
                2. **Ingredient Analysis**:
                - Examine the ingredients of the pantry item to identify any potential allergens.
                - Compare the identified allergens against the list provided by the user.

                3. **Safety Determination**:
                - If any listed allergens are found in the pantry item, it is not safe.
                - If no listed allergens are found, it is considered safe.

                # Output Format

                Responses should be in JSON format, adhering to the following schema:
                ```json
                {
                    "safe_check": true // Replace `true` with `false` if the item might contain allergens.
                }
                ```

                # Examples

                **Example 1:**

                - **Input**: 
                - Pantry item: "Peanut Butter"
                - Potential allergens: ["peanuts", "tree nuts"]

                - **Reasoning**: Peanut Butter contains peanuts, which are in the list of user-provided allergens.
                
                - **Output**:
                ```json
                {
                    "safe_check": false
                }
                ```

                **Example 2:**

                - **Input**:
                - Pantry item: "Rice"
                - Potential allergens: ["peanuts", "tree nuts"]

                - **Reasoning**: Rice does not contain any of the potential allergens listed by the user.
                
                - **Output**:
                ```json
                {
                    "safe_check": true
                }
                ```

                # Notes

                - Ensure careful comparison between the item ingredients and user-provided allergen list, as false negatives could be harmful.
                - Assume the ingredient list of the pantry item is appropriately provided for analysis.
                """
            )
        },
        {
            "role": "user",
            "content": (
                f"The user has these allergies: {allergies_str}. "
                f"Here is the pantry item name: '{item_name}'. "
                f"Based on your knowledge, does this item likely contain any user allergens? "
                f"Return a short JSON with key 'safe_check': true or false."
            )
        }
    ]

    try:
        response = get_openai_client().responses.create(
            model="gpt-4.1-mini",
            input=prompt_messages,
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'safe_check',
                    "schema": {
                            "type": "object",
                            "properties": {
                                "safe_check": {
                                    "type": "boolean"
                                }
                            },
                            "required": ["safe_check"],
                            "additionalProperties": False
                        }
                    }
                }
        )
        gpt_output = response.output_text
        data = json.loads(gpt_output)
        return data.get("safe_check", False)

    except Exception as e:
        logger.error(f"Error checking pantry item with GPT: {e}")
        # fallback: if GPT fails, assume unsafe or safe, your call
        return False

def get_expiring_pantry_items(user, days_threshold=7):
    """
    Returns a list of items that have some quantity available
    and expire within `days_threshold` days.
    """
    today = timezone.now().date()
    threshold_date = today + timedelta(days=days_threshold)
    # Filter by expiration date: must be between today and threshold_date
    filted_pantry_items = user.pantry_items.filter(
        expiration_date__gte=today,  # Must not be expired
        expiration_date__lte=threshold_date  # Must expire within threshold
    ).order_by('expiration_date')
    
    # Then check if there's any available quantity
    expiring_and_available = []
    for item in filted_pantry_items:
        if item.available_quantity() > 0:  # using the property we added
            expiring_and_available.append(item)
    # Then run each item through your GPT-based check
    safe_items = []
    for item in expiring_and_available:
        if not check_item_for_allergies_gpt(item.item_name, user):
            logger.warning(f"Excluding {item.item_name} because GPT flagged it as containing an allergen.")
            continue
        safe_items.append({
            "item_id": item.id,
            "item_name": item.item_name,
            "quantity": item.quantity,
            "expiration_date": item.expiration_date,
            "item_type": item.item_type,
            "notes": item.notes
        })

    return safe_items

def compute_effective_available_items(user, meal_plan, days_threshold=7):
    """
    Returns a dict {pantry_item_id: (leftover_amount, leftover_unit)} for
    soon-to-expire items ONLY. If bridging usage references items not 
    in soon-to-expire, it is ignored.

    leftover_amount = (quantity * weight_per_unit) - bridging_usage

    We assume bridging usage is in the same 'weight_unit' (oz, lb, g, kg)
    as the PantryItem. For each item, we return a tuple:
        (leftover_in_that_unit, item.weight_unit)
    """
    from django.db.models import Sum
    from meals.models import MealPlanMealPantryUsage

    # 1) Fetch soon-to-expire items (only these will be accounted for)
    expiring_list = get_expiring_pantry_items(user, days_threshold=days_threshold)
    # Example of each dict in expiring_list:
    # {
    #   "item_id": 101,
    #   "item_name": "Beef",
    #   "quantity": 4,
    #   "expiration_date": ...,
    #   "item_type": "Canned",
    #   "notes": ...
    # }

    # Build a set of item IDs for quick membership checks
    expiring_ids = {d["item_id"] for d in expiring_list}

    # 2) Build a map of (item_id -> total capacity in the item's unit) AND store PantryItem
    #    This way, we can retrieve each PantryItem's weight_unit later.
    real_availability = {}
    item_map = {}
    for item_info in expiring_list:
        item_id = item_info["item_id"]
        try:
            pantry_item = PantryItem.objects.get(id=item_id)
        except PantryItem.DoesNotExist:
            continue  # If not found, skip

        # quantity is how many containers; weight_per_unit is how many of that unit per container.
        # E.g. 2 containers * 13.5 oz each = 27 oz total.
        weight_each = float(pantry_item.weight_per_unit or 1.0)
        total_capacity = pantry_item.quantity * weight_each

        real_availability[item_id] = total_capacity
        item_map[item_id] = pantry_item

    # 3) Sum bridging usage for these items only
    #    bridging usage is expected to be in the same unit as item.weight_unit
    bridging_qs = (
        MealPlanMealPantryUsage.objects
        .filter(meal_plan_meal__meal_plan=meal_plan, pantry_item__in=expiring_ids)
        .values('pantry_item')
        .annotate(total_used=Sum('quantity_used'))
    )
    usage_dict = {
        row['pantry_item']: float(row['total_used'] or 0.0)
        for row in bridging_qs
    }

    # 4) Compute leftover for each expiring item
    #    leftover is in the item's declared weight_unit
    effective_availability = {}
    for item_id, total_capacity in real_availability.items():
        bridging_used = usage_dict.get(item_id, 0.0)
        leftover_amount = total_capacity - bridging_used
        if leftover_amount < 0:
            leftover_amount = 0.0

        # Retrieve the item's unit (e.g. "oz", "lb", "g", "kg")
        pantry_item = item_map[item_id]
        leftover_unit = pantry_item.weight_unit or ""

        # Store a tuple of (leftover_amount, leftover_unit)
        effective_availability[item_id] = (leftover_amount, leftover_unit)

    return effective_availability

def determine_items_to_replenish(user):
    """
    Determine which items need to be replenished to meet the user's emergency supply goals.
    """
    # Step 1: Get user context
    user_context = generate_user_context(user)
    
    # Step 2: Fetch current pantry items
    pantry_items = user.pantry_items.all()
    pantry_items_dict = {item.item_name.lower(): item.quantity for item in pantry_items}
    pantry_items_str = ', '.join([f"{item.item_name} (x{item.quantity})" for item in pantry_items]) or "None"
    
    # Step 3: Get emergency supply goal
    emergency_supply_goal_days = user.emergency_supply_goal or 0  # Default to 0 if not set
    
    if emergency_supply_goal_days == 0:
        logger.info(f"User {user.username} has no emergency supply goal set.")
        return []  # No items to replenish
    
    # Step 4: Create GPT prompt
    prompt_system = (
        """
        Given the user's context, current pantry items, and emergency supply goal, recommend a list of dried or canned goods the user should replenish to meet their emergency supply goal. Ensure that the recommendations are aligned with the user's dietary preferences, allergies, and goals.

        # Steps

        1. **Understand User Context**: 
        - Gather information on the user's dietary preferences and allergies.
        - Identify the user's specific emergency supply goal in terms of nutritional needs and duration.

        2. **Assess Current Pantry**:
        - Review the list of current pantry items provided by the user.
        - Compare the current pantry items against the emergency supply goal to assess shortfalls.

        3. **Recommend Items**:
        - Recommend dried or canned goods that fill gaps in the current pantry and align with the user's dietary needs.
        - Consider shelf life, nutritional value, and compatibility with dietary restrictions.

        4. **Quantify Recommendations**:
        - Calculate the quantity needed for each recommended item to meet the emergency supply goal.

        # Output Format

        The output should be in JSON format adhering to the ReplenishItemsSchema:

        ```json
        {
        "items_to_replenish": [
            {
            "item_name": "<Name of the item>",
            "quantity": <Quantity integer>,
            "unit": "<Unit of measurement>"
            },
            ...
        ]
        }
        ```

        # Examples

        **Input**: 
        - **User Pantry**: ["rice": 2 kg, "canned beans": 3 cans]
        - **Dietary Preferences**: Vegetarian, gluten-free
        - **Emer. Supply Goal**: 7 days for a family of 4

        **Output**:
        ```json
        {
        "items_to_replenish": [
            {
            "item_name": "canned chickpeas",
            "quantity": 6,
            "unit": "cans"
            },
            {
            "item_name": "quinoa",
            "quantity": 3,
            "unit": "kg"
            }
            ...
        ]
        }
        ```

        # Notes

        - Always respect dietary preferences and allergies when making recommendations.
        - Consider the family size and the duration of the emergency supply when determining quantities.
        - Suggest items with a long shelf life to ensure they remain useful over time.
        """
    )
    
    prompt_user = (
        f"The user has an emergency supply goal of {emergency_supply_goal_days} days.\n"
        f"User Context:\n{user_context}\n"
        f"Current Pantry Items:\n{pantry_items_str}\n"
        "Based on the above information, provide a list of items to replenish in JSON format, following this schema:\n"
        "{\n"
        "  \"items_to_replenish\": [\n"
        "    {\"item_name\": \"string\", \"quantity\": int, \"unit\": \"string\"},\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "Please ensure the items are suitable for long-term storage, align with the user's dietary preferences and allergies, "
        "and help the user meet their emergency supply goal."
    )
    
    # Step 5: Define expected response format using Pydantic
    # (Already defined above with ReplenishItemsSchema)
    
    # Step 6: Call OpenAI API
    try:
        response = get_openai_client().responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "developer", "content": prompt_system},
                {"role": "user", "content": prompt_user},
            ],
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'replenish_items',
                    'schema': ReplenishItemsSchema.model_json_schema()
                }
            }
        )
        assistant_message = response.output_text
        
        # Step 7: Parse and validate GPT response
        try:
            parsed_response = json.loads(assistant_message)
            replenish_items = ReplenishItemsSchema.model_validate(parsed_response)
            return replenish_items.items_to_replenish
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Error parsing GPT response: {e}")
            logger.error(f"Assistant message: {assistant_message}")
            return []
        
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return []
    
def assign_pantry_tags(pantry_item_id):
    try:
        pantry_item = PantryItem.objects.get(id=pantry_item_id)
    except PantryItem.DoesNotExist:
        logger.error(f"Pantry item with ID {pantry_item_id} does not exist.")
        return
    
    prompt = (
        f"You are a helpful assistant. Given a pantry item name '{pantry_item.item_name}' "
        f"and notes '{pantry_item.notes or ''}', suggest a list of tags as JSON:\n"
        f"{{\"tags\": [\"...\"]}}"
    )

    try:
        response = get_openai_client().responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "developer", "content": (
                    """
                    Generate tags for a pantry item in JSON format using the specified schema.

                    You will create a JSON object with a key "tags" which contains a list of strings. Each string should describe the pantry item.

                    # Output Format

                    Output should be in JSON format adhering to the following schema:

                    ```json
                    {
                        "tags": ["tag1", "tag2", "tag3"]
                    }
                    ```

                    Where each item in the list is a descriptive tag for the pantry item. 

                    # Examples

                    **Example 1:**

                    - **Input:** "brown rice"
                    - **Output:** 
                    ```json
                    {
                        "tags": ["whole grain", "rice", "brown"]
                    }
                    ```

                    **Example 2:**

                    - **Input:** "tomato sauce"
                    - **Output:** 
                    ```json
                    {
                        "tags": ["sauce", "tomato", "canned"]
                    }
                    ```

                    (Examples are illustrative and actual tags should match the pantry item's specifics.)

                    # Notes

                    - Ensure that no additional fields are added to the JSON output.
                    - Use concise and relevant tags based on common attributes of the pantry item.
                    - Forbidden to include extra keys or unrelated information in the JSON output.
                    """
                )},
                {"role": "user", "content": prompt}
            ],
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'pantry_tags',
                    'schema': PantryTagsSchema.model_json_schema()
                }
            }
        )

        # The OpenAI response should now be JSON that matches PantryTagsSchema
        response_content = response.output_text
        logger.info(f"Raw OpenAI response for pantry item {pantry_item_id}: {response_content}")

        # Parse and validate with Pydantic
        try:
            tags_data = json.loads(response_content)
            tags_schema = PantryTagsSchema.model_validate(tags_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON for pantry item {pantry_item_id}: {e}")
            return

        # Add tags to the item
        for tag_name in tags_schema.tags:
            tag, created = Tag.objects.get_or_create(name=tag_name.strip())
            pantry_item.tags.add(tag)

        pantry_item.save()
        logger.info(f"Assigned tags {tags_schema.tags} to pantry item {pantry_item_id}")

    except OpenAIError as e:
        logger.error(f"OpenAI API error while assigning tags to pantry item {pantry_item_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while assigning tags to pantry item {pantry_item_id}: {e}")