"""
Focus: Sending emails, notifications, and related external communications.
"""
import json
import logging
import os
import re
import traceback
from datetime import timedelta, datetime, time
from urllib.parse import urlencode
from collections import defaultdict
import pytz
import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import F, Sum
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
from pydantic import ValidationError
from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal, MealPlanInstruction
from meals.pydantic_models import MealPlanApprovalEmailSchema, ShoppingList as ShoppingListSchema
from meals.pantry_management import get_user_pantry_items, get_expiring_pantry_items
from meals.meal_embedding import serialize_data
from meals.serializers import MealPlanSerializer
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, UserSummary, UserDailySummary
from shared.utils import generate_user_context, get_openai_client, _get_language_name
from meals.meal_plan_service import is_chef_meal
from django.template.loader import render_to_string
from meals.meal_assistant_implementation import MealPlanningAssistant
from .celery_utils import handle_task_failure

logger = logging.getLogger(__name__)

@shared_task
@handle_task_failure
def send_meal_plan_approval_email(meal_plan_id):
    from meals.models import MealPlan, MealPlanMeal
    from shared.utils import generate_user_context
    import uuid
    from django.utils import timezone
    import json
    from jinja2 import Environment, FileSystemLoader
    from django.conf import settings
    from urllib.parse import urlencode
    import os

    try:
        # Start a database transaction
        with transaction.atomic():
            meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)
            
            # Assign approval_token if not present
            if not meal_plan.approval_token:
                meal_plan.approval_token = uuid.uuid4()
                meal_plan.token_created_at = timezone.now()
                meal_plan.save()
            
            # Retrieve the full user object
            user = meal_plan.user
            user_name = user.username
            user_email = user.email

            # **Check if the user has opted out of emails**
            if user.unsubscribed_from_emails:
                logger.info(f"User {user.username} has unsubscribed from emails.")
                return  # Do not send the email

            if meal_plan.approval_email_sent:
                logger.info(f"Approval email already sent for MealPlan ID {meal_plan_id}.")
                return  # Do not send the email

        # Proceed with external calls after the transaction is successful
        try:
            user_context = generate_user_context(user)
        except Exception as e:
            logger.error(f"Error generating user context: {e}")
            user_context = "User context not available."

        try:
            preferred_language = _get_language_name(user.preferred_language)
        except Exception as e:
            logger.error(f"Error fetching preferred language for user {user.username}: {e}")
            preferred_language = "English"

        # Generate the approval link with query parameters
        approval_token = meal_plan.approval_token
        base_approval_url = f"{os.getenv('STREAMLIT_URL')}/meal_plans"

        # Create approval links with meal prep preferences
        query_params_daily = urlencode({
            'approval_token': approval_token,
            'meal_prep_preference': 'daily'
        })
        query_params_one_day = urlencode({
            'approval_token': approval_token,
            'meal_prep_preference': 'one_day_prep'
        })

        approval_link_daily = f"{base_approval_url}?{query_params_daily}"
        approval_link_one_day = f"{base_approval_url}?{query_params_one_day}"

        # Fetch the meals associated with the meal plan
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')

        # Create the meals_list
        meals_list = []
        for meal in meal_plan_meals:
            meals_list.append({
                "meal_name": meal.meal.name,
                "meal_type": meal.meal_type,
                "day": meal.day,
                "description": meal.meal.description or "A delicious meal prepared for you.",
                "nutrition": meal.meal.macro_info if hasattr(meal.meal, 'macro_info') else None,
            })

        # Sort the meals_list by day and meal type
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        meal_type_order = ['Breakfast', 'Lunch', 'Dinner']
        day_order_map = {day: index for index, day in enumerate(day_order)}
        meal_type_order_map = {meal_type: index for index, meal_type in enumerate(meal_type_order)}
        meals_list.sort(key=lambda x: (
            day_order_map.get(x['day'], 7),
            meal_type_order_map.get(x['meal_type'], 3)
        ))

        # Build a comprehensive, detailed message for the assistant
        message_content = (
            f"I need to send a meal plan approval email to {user_name}. Here's all the context you'll need:\n\n"
            f"USER CONTEXT: {user_context}\n\n"
            f"MEAL PLAN DETAILS:\n"
            f"- Week: {meal_plan.week_start_date.strftime('%B %d, %Y')} to {meal_plan.week_end_date.strftime('%B %d, %Y')}\n"
            f"- Preference: {meal_plan.meal_prep_preference if meal_plan.meal_prep_preference else 'Not specified'}\n"
            f"- Dietary restrictions: {user.dietary_restrictions if hasattr(user, 'dietary_restrictions') else 'None specified'}\n\n"
            f"APPROVAL LINKS:\n"
            f"- Daily prep: {approval_link_daily}\n"
            f"- One-day bulk prep: {approval_link_one_day}\n\n"
            f"MEALS (sorted by day and meal type):\n"
        )

        # Group meals by day for better organization
        meals_by_day = {}
        for meal in meals_list:
            day = meal['day']
            if day not in meals_by_day:
                meals_by_day[day] = []
            meals_by_day[day].append(meal)

        # Add each day's meals to the message
        for day in day_order:
            if day in meals_by_day:
                message_content += f"\n{day}:\n"
                for meal in meals_by_day[day]:
                    message_content += f"- {meal['meal_type']}: {meal['meal_name']}"
                    if meal['description'] and meal['description'] != "A delicious meal prepared for you.":
                        message_content += f" - {meal['description']}"
                    message_content += "\n"

        # Add nutrition information if available
        message_content += "\nNUTRITION INFORMATION:\n"
        has_nutrition = False
        for meal in meals_list:
            if meal.get('nutrition'):
                has_nutrition = True
                message_content += f"- {meal['meal_name']}: {meal['nutrition']}\n"
        
        if not has_nutrition:
            message_content += "Detailed nutrition information not available for these meals.\n"

        # Add user goals if available
        try:
            from customer_dashboard.models import GoalTracking
            goals = GoalTracking.objects.filter(user=user).first()
            if goals:
                message_content += f"\nUSER GOALS:\n{goals.goal_description}\n\n"
        except Exception as e:
            logger.error(f"Error retrieving user goals: {e}")

        # Send the notification via the assistant
        subject = f'Approve Your Meal Plan for {meal_plan.week_start_date.strftime("%b %d")} - {meal_plan.week_end_date.strftime("%b %d")}'
        
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject
        )
        
        # Mark as sent if successful
        if result.get('status') == 'success':
            with transaction.atomic():
                meal_plan.approval_email_sent = True
                meal_plan.save()
            logger.info(f"Meal plan approval email sent via assistant for: {user.email}")
        else:
            logger.error(f"Error sending meal plan approval email via assistant for: {user.email}, error: {str(result)}")

    except Exception as e:
        logger.error(f"Error in send_meal_plan_approval_email: {e}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'meal_plan_approval_email',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)

@shared_task
@handle_task_failure
def generate_shopping_list(meal_plan_id):
    from django.db.models import Sum
    from meals.models import MealPlan, ShoppingList as ShoppingListModel, MealPlanMealPantryUsage, PantryItem, MealAllergenSafety
    # Import is_chef_meal locally to avoid circular imports
    from meals.meal_plan_service import is_chef_meal
    from collections import defaultdict # Ensure defaultdict is imported
    
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)

    # Serialize the meal plan data
    serializer = MealPlanSerializer(meal_plan)
    meal_plan_data = serializer.data

    # Extract user information
    user_info = meal_plan_data.get('user', {})
    user_email = user_info.get('email')
    user_name = user_info.get('username')

    # Retrieve the full user object
    user_id = meal_plan_data.get('user', {}).get('id')
    if not user_id:
        logger.error(f"User not found for MealPlan ID {meal_plan_id}.")
        return

    user = CustomUser.objects.get(id=user_id)

    # Retrieve the user's preferred serving size
    try:
        household_member_count = user.household_member_count
    except Exception as e:
        logger.error(f"Error retrieving household member count for user {user.id}: {e}")
        household_member_count = 1

    # Collect all ingredient substitution information from the meal plan
    substitution_info = []
    chef_meals_present = False
    meal_plan_meals = meal_plan.meal.all()
    
    # Initialize substitution_str early so it's available throughout the function
    substitution_str = ""
    
    for meal in meal_plan_meals:
        # Check if this is a chef meal
        is_chef = is_chef_meal(meal)
        if is_chef:
            chef_meals_present = True
            logger.info(f"Meal '{meal.name}' is chef-created, not providing substitutions in shopping list")
            continue
            
        # Get allergen safety checks that include substitution information
        allergen_checks = MealAllergenSafety.objects.filter(
            meal=meal, 
            user=user,
            is_safe=False,  # We only need substitutions for unsafe meals
        ).exclude(substitutions__isnull=True).exclude(substitutions={})
        
        for check in allergen_checks:
            if check.substitutions:
                for original_ingredient, substitutes in check.substitutions.items():
                    if substitutes:  # Make sure there are actual substitutions
                        sub_info = {
                            "meal_name": meal.name,
                            "original_ingredient": original_ingredient,
                            "substitutes": substitutes,
                            "notes": f"For {meal.name}, replace {original_ingredient} with {', '.join(substitutes)}"
                        }
                        substitution_info.append(sub_info)
    
    # Retrieve bridging usage for leftover logic
    bridging_qs = (
        MealPlanMealPantryUsage.objects
        .filter(meal_plan_meal__meal_plan=meal_plan)
        .values('pantry_item')
        .annotate(total_used=Sum('quantity_used'))
    )
    bridging_usage_dict = {row['pantry_item']: float(row['total_used'] or 0.0) for row in bridging_qs}

    # Convert bridging usage into leftover info
    leftover_info_list = []
    for pantry_item_id, used_qty in bridging_usage_dict.items():
        try:
            pi = PantryItem.objects.get(id=pantry_item_id)
        except PantryItem.DoesNotExist:
            continue

        total_capacity = pi.quantity * float(pi.weight_per_unit or 1.0)
        leftover_amount = total_capacity - used_qty
        if leftover_amount < 0:
            leftover_amount = 0.0
        leftover_info_list.append(
            f"{pi.item_name} leftover: {leftover_amount} {pi.weight_unit or ''}"
        )
    bridging_leftover_str = "; ".join(leftover_info_list) if leftover_info_list else "No leftover data available"

    # Retrieve user pantry items
    try:
        user_pantry_items = get_user_pantry_items(user)
    except Exception as e:
        logger.error(f"Error retrieving pantry items for user {user.id}: {e}")
        user_pantry_items = []

    # Retrieve expiring items
    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        # Assuming each item in expiring_pantry_items is a dict with a 'name' field
        expiring_items_str = ', '.join(item['name'] for item in expiring_pantry_items) if expiring_pantry_items else 'None'
    except Exception as e:
        logger.error(f"Error retrieving expiring pantry items for user {user.id}: {e}")
        traceback.print_exc()
        expiring_pantry_items = []
        expiring_items_str = 'None'

    # Determine items to replenish
    # (removed)

    # Generate user context
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = 'No additional user context provided.'

    # Initialize or fetch any existing shopping list
    shopping_list = None
    existing_shopping_list = ShoppingListModel.objects.filter(meal_plan=meal_plan).first()

    if existing_shopping_list:
        logger.info(f"Shopping list already exists for MealPlan ID {meal_plan_id}. Sending existing list.")
        shopping_list = existing_shopping_list.items
    else:
        # Generate a new shopping list
        try:
            user_data_json = serialize_data(meal_plan_data)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            return

        try:
            # NOTE: We assume `client` is already available in your environment.
            # No need to import it here as requested.
            from meals.pydantic_models import ShoppingCategory
            shopping_category_list = [item.value for item in ShoppingCategory]
            
            # Format substitution information for prompt
            if substitution_info:
                substitution_str = "Ingredient substitution information:\n"
                for sub in substitution_info:
                    substitution_str += f"- In {sub['meal_name']}, replace {sub['original_ingredient']} with {', '.join(sub['substitutes'])}\n"
            
            # Add chef meal note if needed
            chef_note = ""
            if chef_meals_present:
                chef_note = "IMPORTANT: Some meals in this plan are chef-created and must be prepared exactly as specified. Do not suggest substitutions for chef-created meals. Include all ingredients for chef meals without alternatives."
            
            response = get_openai_client().responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "developer",
                        "content": "You are a helpful assistant that generates shopping lists in JSON format."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Answering in the user's preferred language: {_get_language_name(user_info.get('preferred_language', 'English'))},"
                            f"Generate a shopping list based on the following meals: {json.dumps(user_data_json)}. "
                            f"The user information is as follows: {user_context}. "
                            f"Bridging leftover info if user follows their meal plan: {bridging_leftover_str}. "
                            f"The leftover amounts are calculated based on the user's pantry items and the meals they plan to prepare. "
                            f"Based on the leftover amounts in relation to the required servings, the user may not need to purchase additional items. "
                            f"The user has the following items in their pantry: {', '.join(user_pantry_items)}. "
                            f"The user needs to serve {household_member_count} household members total. Pay special attention to individual household member dietary needs, preferences, allergies, and ages from the user context when adjusting quantities and recommending alternatives. Consider that different household members may have different portion requirements and dietary restrictions. "
                            f"Please ensure the quantities are as realistic as possible to grocery store quantities. "
                            f"The user has these pantry items expiring soon: {expiring_items_str}. "
                            f"Available shopping categories: {shopping_category_list}. "
                            f"Do not include these expiring items in the shopping list unless they truly need to be replenished for the sake of the meals. "
                            f"\n\n{substitution_str}\n"
                            f"{chef_note}\n"
                            f"IMPORTANT: For ingredients in non-chef meals that have substitution options, please include BOTH the original ingredient AND its substitutes in the shopping list, "
                            f"clearly marking them as alternatives to each other so the user can choose which one to buy. "
                            f"Format alternatives as separate items with a note like 'Alternative to X for [meal name]'."
                        )
                    }
                ],
                #store=True,
                #metadata={'tag': 'shopping_list'},
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'shopping_list',
                        'schema': ShoppingListSchema.model_json_schema()
                    }
                }
            )
            shopping_list = response.output_text

            if hasattr(meal_plan, 'shopping_list'):
                meal_plan.shopping_list.update_items(shopping_list)
            else:
                ShoppingListModel.objects.create(meal_plan=meal_plan, items=shopping_list)

        except ValidationError as e:
            logger.error(f"Error parsing shopping list: {e}")
        except Exception as e:
            logger.error(f"Unexpected error generating shopping list for meal plan {meal_plan_id}: {e}")

    # Attempt to parse the GPT JSON
    if not shopping_list:
        logger.error(f"Failed to generate shopping list for MealPlan ID {meal_plan_id}.")
        return

    try:
        shopping_list_dict = json.loads(shopping_list)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse shopping list as JSON: {e}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'shopping_list',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        return

    # Group items by category and aggregate quantities
    categorized_items = defaultdict(lambda: defaultdict(lambda: {'quantity': 0, 'unit': '', 'notes': []}))

    for item in shopping_list_dict.get("items", []):
        logger.info(f"Shopping list item: {item}")
        category = item.get("category", "Miscellaneous")
        ingredient = item.get("ingredient")
        quantity_str = item.get("quantity", "")
        unit = item.get("unit", "")
        meal_name = item.get("meal_name", "")
        notes = item.get("notes", "")

        # Handle fractional quantities
        try:
            if '/' in quantity_str:
                numerator, denominator = quantity_str.split('/')
                quantity = float(numerator) / float(denominator)
            else:
                quantity = float(quantity_str)
        except ValueError:
            quantity = None
            logger.info(f"Non-numeric quantity '{quantity_str}' for ingredient '{ingredient}'")

        if quantity is not None:
            if categorized_items[category][ingredient]['unit'] == unit or not categorized_items[category][ingredient]['unit']:
                categorized_items[category][ingredient]['quantity'] += quantity
                categorized_items[category][ingredient]['unit'] = unit
            else:
                # If units differ, treat them as separate entries
                if categorized_items[category][ingredient]['unit']:
                    logger.warning(
                        f"Conflicting units for {ingredient} in {category}: "
                        f"{categorized_items[category][ingredient]['unit']} vs {unit}"
                    )
                categorized_items[category][ingredient]['quantity'] += quantity
                categorized_items[category][ingredient]['unit'] += f" and {quantity} {unit}"
        else:
            # For e.g. "To taste"
            if not categorized_items[category][ingredient]['unit']:
                categorized_items[category][ingredient]['quantity'] = quantity_str
                categorized_items[category][ingredient]['unit'] = unit

        # Append any relevant notes
        if notes and 'none' not in notes.lower():
            categorized_items[category][ingredient]['notes'].append(f"{meal_name}: {notes} ({quantity_str} {unit})")

    # Build the final message for the assistant (regular shopping list only)
    try:
        from meals.meal_assistant_implementation import MealPlanningAssistant

        # Format the safe items into a simpler structure for the template
        safe_items_data = []
        for pi in user_pantry_items:
            # Handle both PantryItem objects and strings
            if isinstance(pi, str):
                safe_items_data.append({
                    "item_name": pi,
                    "quantity_available": "Unknown",
                    "unit": "",
                    "notes": "",
                })
            else:
                # Assume it's a PantryItem object with attributes
                safe_items_data.append({
                    "item_name": getattr(pi, 'item_name', str(pi)),
                    "quantity_available": getattr(pi, 'quantity', "Unknown"),
                    "unit": getattr(pi, 'weight_unit', "") or "",
                    "notes": getattr(pi, 'notes', "") or "",
                })

        # Add information about current safe pantry items
        if safe_items_data:
            message_content = "CURRENT SAFE PANTRY ITEMS:\n"
            for item in safe_items_data:
                message_content += f"- {item['item_name']}: {item['quantity_available']} {item['unit'] or 'units'}"
                if item['notes']:
                    message_content += f" (Note: {item['notes']})"
                message_content += "\n"
            message_content += "\n"
        else:
            message_content = "CURRENT SAFE PANTRY ITEMS: None available\n\n"

        # Build the final message for the assistant (regular shopping list only)
        # Inserted block as per instructions
        # ---------------------------------------------------------------
        # Build the final message for the assistant (regular shopping list only)
        message_content = (
            f"I need to send a shopping list to {user_name} for their meal plan from "
            f"{meal_plan.week_start_date.strftime('%B %d')} to {meal_plan.week_end_date.strftime('%B %d')}. "
            "Here's the context you'll need:\n\n"
            f"USER CONTEXT:\n{user_context}\n\n"
            f"MEAL PLAN DETAILS:\n"
            f"- Time period: {meal_plan.week_start_date.strftime('%B %d, %Y')} to "
            f"{meal_plan.week_end_date.strftime('%B %d, %Y')}\n"
            f"- Serving size: {household_member_count} "
            f"{'people' if household_member_count > 1 else 'person'}\n"
            f"- Dietary restrictions: {user.dietary_restrictions if hasattr(user, 'dietary_restrictions') else 'None specified'}\n\n"
            f"PANTRY INFORMATION:\n"
            f"- Expiring items: {expiring_items_str}\n"
            f"- Inventory: {', '.join(user_pantry_items) if user_pantry_items else 'No items in pantry'}\n"
            f"- Leftover usage: {bridging_leftover_str}\n\n"
            f"MEAL SUBSTITUTIONS:\n"
            f"{substitution_str if substitution_info else 'No substitutions needed for this meal plan.'}\n\n"
            "SHOPPING LIST ITEMS BY CATEGORY:\n"
        )

        # Append the categorized items
        if categorized_items:
            for category, items_in_category in categorized_items.items():
                if items_in_category:
                    message_content += f"\n{category.upper()}:\\n"
                    for ingredient, details in items_in_category.items():
                        qty = details['quantity']
                        unit = details['unit']
                        notes_list = details.get('notes', [])

                        # Format quantity nicely
                        if isinstance(qty, (int, float)):
                            qty_str = (f"{qty:.1f}".rstrip('0').rstrip('.') 
                                       if qty % 1 != 0 else f"{int(qty)}")
                        else:
                            qty_str = str(qty)

                        message_content += f"- {ingredient}: {qty_str} {unit}"
                        if notes_list:
                            message_content += f" (Notes: {'; '.join(notes_list)})"
                        message_content += "\\n"
            message_content += "\\n"
        else:
            message_content += "No items in shopping list.\\n\\n"
        # ---------------------------------------------------------------

        subject = f"Your Shopping List for {meal_plan.week_start_date.strftime('%b %d')} - {meal_plan.week_end_date.strftime('%b %d')}"

        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject
        )

        if result.get('status') == 'success':
            logger.info(f"Shopping list sent via assistant for: {user_email}")
        else:
            logger.error(f"Error sending shopping list via assistant for: {user_email}, error: {str(result)}")

    except Exception as e:
        logger.error(f"Error sending shopping list via assistant for: {user_email}, error: {str(e)}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'shopping_list',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)

@shared_task
@handle_task_failure
def generate_user_summary(user_id: int, summary_date=None) -> None:
    """
    Build (or rebuild) a high-level daily user summary in the user's
    preferred language and store it on ``UserDailySummary``.
    
    Args:
        user_id: The ID of the user to generate a summary for
        summary_date: The date for the summary (defaults to today in user's timezone)
    """
    from customer_dashboard.models import UserDailySummary
    from shared.utils import generate_user_context
    from django.utils import timezone
    from openai import OpenAI, OpenAIError
    import hashlib
    import json
    
    user = get_object_or_404(CustomUser, id=user_id)
    user_context = generate_user_context(user)
    
    # Get or create summary_date (default to today in user's local timezone)
    if summary_date is None:
        # Use the user's timezone if available, otherwise use UTC
        user_timezone = pytz.timezone(user.timezone if user.timezone else 'UTC')
        summary_date = timezone.now().astimezone(user_timezone).date()
    elif isinstance(summary_date, str):
        # If it's a string, parse it as a date
        summary_date = datetime.strptime(summary_date, '%Y-%m-%d').date()
    
    # Use select_for_update with transaction to prevent race conditions
    with transaction.atomic():
        summary, created = UserDailySummary.objects.select_for_update().get_or_create(
            user=user,
            summary_date=summary_date,
            defaults={'status': UserDailySummary.PENDING}
        )
        
        # If status is ERROR, allow regeneration
        if not created and summary.status == UserDailySummary.ERROR:
            summary.status = UserDailySummary.PENDING
            summary.save(update_fields=["status"])
    
    # For backward compatibility, also update the legacy UserSummary
    legacy_summary, _ = UserSummary.objects.get_or_create(user=user)
    legacy_summary.status = "pending"
    legacy_summary.save(update_fields=["status"])

    # Gather data for yesterday (if today) or for the specific date
    if summary_date == timezone.now().date():
        # For today's summary, get data from yesterday
        data_start_date = timezone.now() - timedelta(days=1)
        yesterday = timezone.now().date() - timedelta(days=1)
        data_end_date = timezone.now()
        time_period_description = "In the last 24 hours"
    else:
        # For historical date, get data for that specific date
        data_start_date = datetime.combine(summary_date, time.min)
        data_start_date = timezone.make_aware(data_start_date)
        data_end_date = datetime.combine(summary_date, time.max)
        data_end_date = timezone.make_aware(data_end_date)
        time_period_description = f"On {summary_date.strftime('%A, %B %d')}"

    # Get user data for the specified date range
    goals = GoalTracking.objects.filter(user=user)
    user = CustomUser.objects.get(id=user_id)
    metrics = UserHealthMetrics.objects.filter(
        user=user, 
        date_recorded__gte=data_start_date,
        date_recorded__lte=data_end_date
    )
    calories = CalorieIntake.objects.filter(
        user=user, 
        date_recorded__gte=data_start_date,
        date_recorded__lte=data_end_date
    )

    data_bundle = {
        "user_profile": user_context,
        "goals": [
            {"name": g.goal_name, "description": g.goal_description} for g in goals
        ],
        "health_metrics": [
            {
                "date": m.date_recorded.isoformat(timespec="seconds"),
                "weight_kg": float(m.weight) if m.weight else None,
                "weight_lbs": round(float(m.weight) * 2.20462, 1) if m.weight else None,
                "bmi": m.bmi,
                "mood": m.mood,
                "energy_level": m.energy_level,
            }
            for m in metrics
        ],
        "calorie_intake": [
            {
                "meal": c.meal_name,
                "description": c.meal_description,
                "portion_size": c.portion_size,
                "date": c.date_recorded.isoformat(timespec="seconds"),
            }
            for c in calories
        ],
        "meal_plan_needs_approval": not user.mealplan_set.filter(is_approved=True).exists(),
    }
    
    # Calculate data hash for idempotency check
    data_hash = hashlib.sha256(json.dumps(data_bundle, sort_keys=True).encode()).hexdigest()
    
    # If hash matches and status is completed, no need to regenerate
    if summary.data_hash == data_hash and summary.status == UserDailySummary.COMPLETED:
        return
    
    # Update hash and status
    summary.data_hash = data_hash
    summary.status = UserDailySummary.PENDING
    summary.save(update_fields=["data_hash", "status"])

    system_prompt = (
        "You are a friendly, motivating wellness assistant named MJ.\n"
        f"Write a daily summary for the user **in {_get_language_name(user.preferred_language)}**.\n"
        f"• Focus on {time_period_description}\n"
        f"• Warm greeting with the user's name {user.username}.\n"
        "• Overview ≤ 5 sentences.\n"
        "• Sections: 1) Goals & Status, 2) Health Metrics trends, 3) Calorie-Intake insights.\n"
        "• Omit any empty section.\n"
        "• If meal_plan_needs_approval is true, add one gentle reminder at the end.\n"
        "• Encouraging, business-casual tone.\n"
        f"• Respond ONLY in {_get_language_name(user.preferred_language)}."
    )

    try:
        resp = get_openai_client().responses.create(
            model="gpt-4.1-nano",
            input=[
                {
                    "role": "developer",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        f"{time_period_description}, here is the relevant data:\n"
                        f"{data_bundle}"
                    ),
                },
            ],
            temperature=0.7,
            # metadata={"tag": "user_summary"},  # uncomment if you're tagging
        )

        summary.summary = resp.output_text
        summary.status = UserDailySummary.COMPLETED
        
        # Also update the legacy summary for backward compatibility
        legacy_summary.summary = resp.output_text
        legacy_summary.status = "completed"
        
    except OpenAIError as err:
        summary.status = UserDailySummary.ERROR
        summary.summary = f"OpenAI error: {err}"
        
        legacy_summary.status = "error"
        legacy_summary.summary = f"OpenAI error: {err}"
        # n8n traceback
        n8n_traceback = {
            'error': str(err),
            'source': 'user_summary',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
    except Exception as exc:
        summary.status = UserDailySummary.ERROR
        summary.summary = f"Unhandled error: {exc}"
        
        legacy_summary.status = "error"
        legacy_summary.summary = f"Unhandled error: {exc}"
        # n8n traceback
        n8n_traceback = {
            'error': str(exc),
            'source': 'user_summary',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)    # n8n traceback

    summary.save()
    legacy_summary.save()

def mark_summary_stale(user, date=None):
    """
    Mark a user's daily summary as stale and trigger regeneration.
    
    Args:
        user: The user whose summary should be marked as stale
        date: The date of the summary to mark as stale (defaults to today)
    """
    from customer_dashboard.models import UserDailySummary
    from django.utils import timezone
    
    date = date or timezone.localdate()
    
    obj, _ = UserDailySummary.objects.get_or_create(
        user=user, 
        summary_date=date
    )
    obj.status = UserDailySummary.PENDING
    obj.save(update_fields=["status"])
    
    # Trigger regeneration asynchronously
    generate_user_summary.delay(user.id, date.strftime('%Y-%m-%d'))

@shared_task
@handle_task_failure
def generate_emergency_supply_list(user_id):
    """
    Creates or updates an emergency supply list for the user,
    ensuring they have enough non-perishable items for `emergency_supply_goal` days * `household_member_count`.
    Excludes items that GPT flags as containing allergens.
    Then sends the final result via email or n8n.
    """
    from custom_auth.models import CustomUser
    from meals.models import PantryItem
    from meals.meal_plan_service import get_user_allergies
    from meals.pantry_management import check_item_for_allergies_gpt
    from shared.utils import generate_user_context
    from jinja2 import Environment, FileSystemLoader

    user = get_object_or_404(CustomUser, id=user_id)

    if not user.emergency_supply_goal or user.emergency_supply_goal <= 0:
        return

    days_of_supply = user.emergency_supply_goal
    household_member_count = user.household_member_count or 1
    total_serving_days = days_of_supply * household_member_count

    # 1) Gather shelf-stable items
    shelf_stable_types = ["Canned", "Dry"]
    pantry_queryset = PantryItem.objects.filter(
        user=user,
        item_type__in=shelf_stable_types
    )

    # 2) Filter out items with allergens (GPT check)
    safe_pantry_items = []
    for pi in pantry_queryset:
        if check_item_for_allergies_gpt(pi.item_name, user):
            safe_pantry_items.append(pi)
        else:
            logger.debug(f"EMAIL SERVICE DEBUG: Excluding {pi.item_name} from {user.username}'s emergency supply (potential allergen).")

    # 3) Summarize the user's safe pantry items
    user_emergency_pantry_summary = []
    for pi in safe_pantry_items:
        weight_each = float(pi.weight_per_unit or 1.0)
        total_capacity = pi.quantity * weight_each
        item_summary = {
            "item_name": pi.item_name,
            "item_type": pi.item_type,
            "unit": pi.weight_unit,
            "quantity_available": pi.quantity,
            "weight_per_unit": weight_each,
            "total_capacity_in_unit": total_capacity
        }
        user_emergency_pantry_summary.append(item_summary)

    # 4) GPT call
    user_context = generate_user_context(user) or 'No additional user context.'
    user_allergies = get_user_allergies(user)
    pantry_summary_json = json.dumps(user_emergency_pantry_summary)

    try:
        from meals.pydantic_models import EmergencySupplyList
        response = get_openai_client().responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "developer",
                    "content": (
                        """
                        Generate an emergency supply list in JSON format following a specified schema. Each item should be detailed, without including any default values, and should adhere strictly to the provided JSON schema format.

                        # Steps

                        1. **Identify Supply Items**: Determine the essential items needed for an emergency based on common requirements such as food, water, medical supplies, and other essentials.
                        2. **Specify Quantities and Units**: Clearly specify the quantity needed for each item and the unit of measurement when applicable.
                        3. **Include Additional Notes**: Provide any relevant notes for each item or for the entire list if necessary.
                        4. **Structure According to Schema**: Ensure that the JSON output strictly follows the schema specified, without including any extra properties or default values.

                        # Output Format

                        Ensure the output is in valid JSON format structured as follows:

                        ```json
                        {
                        "emergency_list": [
                            {
                            "item_name": "string",
                            "quantity_to_buy": "string",
                            "unit": "string",
                            "notes": "string"
                            }
                        ],
                        "notes": "string"
                        }
                        ```
                        - **`emergency_list`**: An array of objects, each describing an item.
                        - **`item_name`**: Name of the item.
                        - **`quantity_to_buy`**: The quantity that should be purchased or prepared.
                        - **`unit`**: The unit of measurement relevant to the item.
                        - **`notes`**: Any additional notes about the item or overarching comments for the entire list.

                        # Examples

                        **Example 1**

                        Input:
                        - Determine items for a basic emergency kit.

                        Output:
                        ```json
                        {
                        "emergency_list": [
                            {
                            "item_name": "Water",
                            "quantity_to_buy": "10",
                            "unit": "liters",
                            "notes": "At least one gallon per person per day for 3 days"
                            },
                            {
                            "item_name": "Canned Food",
                            "quantity_to_buy": "15",
                            "unit": "cans",
                            "notes": "Ensure they have easy-open lids"
                            }
                        ],
                        "notes": "This list is a starting checklist for a simple emergency kit."
                        }
                        ```

                        **Example 2**

                        Input:
                        - Items for a medical emergency kit.

                        Output:
                        ```json
                        {
                        "emergency_list": [
                            {
                            "item_name": "First Aid Kit",
                            "quantity_to_buy": "1",
                            "unit": null,
                            "notes": "Should include bandages, antiseptics, and medications"
                            },
                            {
                            "item_name": "Prescription medication",
                            "quantity_to_buy": "30",
                            "unit": "days supply",
                            "notes": "Ensure extra medication for prolonged emergencies"
                            }
                        ],
                        "notes": "Medical necessities for handling common injuries and health issues."
                        }
                        ```

                        # Notes

                        - Avoid including any default values in the JSON output.
                        - Ensure units are specified where applicable, and `unit` can be null if not relevant.
                        - Follow the schema strictly, with no additional properties or data beyond what is specified.                        
                        """
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"User context: {user_context}\n\n"
                        f"Allergies: {', '.join(user_allergies) if user_allergies else 'None'}\n\n"
                        f"The user wants enough shelf-stable items for {days_of_supply} days, "
                        f"covering {household_member_count} household members with individual dietary needs, i.e. a total of {total_serving_days} 'servings.' Consider individual dietary preferences and ages when recommending items.\n"
                        f"Current safe items in their pantry:\n{pantry_summary_json}\n\n"
                        "Generate a JSON response specifying which additional items they should buy (approx. quantity/units) "
                        "to meet the user's emergency supply goal, ensuring no allergens are included. "
                        "Focus on dry/canned staples."
                    )
                }
            ],
            #store=True,
            #metadata={'tag': 'emergency-supply-list'},
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'emergency_supply_list',
                    "schema": EmergencySupplyList.model_json_schema()
                }
            }
        )

        gpt_output_str = response.output_text
        
        try:
            emergency_supply_data = json.loads(gpt_output_str)
            emergency_list = emergency_supply_data.get("emergency_list", [])
            notes = emergency_supply_data.get("notes", "")
        except json.JSONDecodeError:
            logger.warning("EMAIL SERVICE DEBUG: GPT output was not valid JSON; storing raw text.")
            emergency_list = []
            notes = f"GPT returned non-JSON output: {gpt_output_str}"

        # Format the safe items into a simpler structure for the template
        safe_items_data = []
        for pi in safe_pantry_items:
            # Handle both PantryItem objects and strings
            if isinstance(pi, str):
                safe_items_data.append({
                    "item_name": pi,
                    "quantity_available": "Unknown",
                    "unit": "",
                    "notes": "",
                })
            else:
                # Assume it's a PantryItem object with attributes
                safe_items_data.append({
                    "item_name": getattr(pi, 'item_name', str(pi)),
                    "quantity_available": getattr(pi, 'quantity', "Unknown"),
                    "unit": getattr(pi, 'weight_unit', "") or "",
                    "notes": getattr(pi, 'notes', "") or "",
                })

        # Send via MealPlanningAssistant instead of n8n
        try:
            from meals.meal_assistant_implementation import MealPlanningAssistant
            
            # Add information about current safe pantry items
            if safe_items_data:
                message_content = "CURRENT SAFE PANTRY ITEMS:\n"
                for item in safe_items_data:
                    message_content += f"- {item['item_name']}: {item['quantity_available']} {item['unit'] or 'units'}"
                    if item['notes']:
                        message_content += f" (Note: {item['notes']})"
                    message_content += "\n"
                message_content += "\n"
            else:
                message_content = "CURRENT SAFE PANTRY ITEMS: None available\n\n"
            
            # Add recommended emergency supplies to purchase
            if emergency_list:
                message_content += "RECOMMENDED EMERGENCY SUPPLIES TO PURCHASE:\n"
                for item in emergency_list:
                    try:
                        # Access attributes safely based on type
                        if isinstance(item, dict):
                            item_name = item.get('item_name', 'Unknown item')
                            quantity = item.get('quantity_to_buy', '')
                            unit = item.get('unit', '')
                            notes = item.get('notes', '')
                        else:
                            # Assume it's a Pydantic model or similar object with attributes
                            item_name = getattr(item, 'item_name', 'Unknown item') 
                            quantity = getattr(item, 'quantity_to_buy', '')
                            unit = getattr(item, 'unit', '')
                            notes = getattr(item, 'notes', '')
                            
                        message_content += f"- {item_name}: {quantity} {unit or ''}"
                        if notes:
                            message_content += f" (Note: {notes})"
                    except Exception as e:
                        logger.error(f"EMAIL SERVICE DEBUG: Error formatting emergency item: {e}")
                        message_content += f"- {str(item)}\n"
                    
                    message_content += "\n"
                message_content += "\n"
            else:
                message_content += "RECOMMENDED EMERGENCY SUPPLIES: No additional items needed\n\n"
            
            # Add overall notes if available
            if notes:
                message_content += f"ADDITIONAL NOTES:\n{notes}\n\n"
            
            # Get regular shopping list items if available
            try:
                from meals.models import MealPlan, ShoppingList as ShoppingListModel # Alias to avoid conflict
                from collections import defaultdict # Ensure defaultdict is imported
                recent_meal_plan = MealPlan.objects.filter(
                    user=user,
                    # is_active=True # Consider if you only want active meal plans
                ).order_by('-created_date').first()
                
                if recent_meal_plan:
                    shopping_list_obj = ShoppingListModel.objects.filter(meal_plan=recent_meal_plan).first()
                    if shopping_list_obj and shopping_list_obj.items:
                        try:
                            shopping_data = json.loads(shopping_list_obj.items)
                            shopping_items = shopping_data.get('items', [])
                            if shopping_items:
                                by_category = defaultdict(list)
                                for item_sl in shopping_items:
                                    category = item_sl.get('category', 'Miscellaneous')
                                    by_category[category].append(item_sl)
                                
                                message_content += "\nREGULAR SHOPPING LIST (from your latest meal plan):\n"
                                for category, cat_items in by_category.items():
                                    message_content += f"\n{category.upper()}:\n"
                                    for item_detail in cat_items:
                                        ingredient = item_detail.get('ingredient', 'Unknown item')
                                        quantity = item_detail.get('quantity', '')
                                        unit = item_detail.get('unit', '')
                                        item_notes = item_detail.get('notes', '')
                                        
                                        message_content += f"- {ingredient}: {quantity} {unit}"
                                        if item_notes:
                                            message_content += f" (Note: {item_notes})"
                                        message_content += "\n"
                                message_content += "\n"
                        except json.JSONDecodeError:
                            logger.warning(f"EMAIL SERVICE DEBUG: Could not parse regular shopping list for user {user.id}: invalid JSON")
                        except Exception as e_sl_parse:
                            logger.warning(f"EMAIL SERVICE DEBUG: Error processing regular shopping list for user {user.id}: {e_sl_parse}")
            except Exception as e_sl_fetch:
                logger.warning(f"EMAIL SERVICE DEBUG: Error retrieving regular shopping list data for user {user.id}: {e_sl_fetch}")
            
            # Add emergency preparedness tips
            message_content += (
                "Please craft a helpful email about emergency food preparedness that includes the list of items the user "
                "should purchase. Explain why having these emergency supplies is important and include practical tips for "
                "storage and rotation. Make sure to acknowledge any allergies and explain how the recommended items account "
                "for those restrictions. The tone should be informative and supportive, not alarmist."
            )
            # Ensure the AI is prompted to include BOTH lists
            message_content += "\n\nPlease also include the REGULAR SHOPPING LIST items if they were provided above, clearly distinguishing them from the emergency supplies."
            
            subject = f"Your Emergency Supply List for {days_of_supply} Days"
            
            result = MealPlanningAssistant.send_notification_via_assistant(
                user_id=user.id,
                message_content=message_content,
                subject=subject
            )
            
            if result.get('status') == 'success':
                pass
            else:
                logger.error(f"EMAIL SERVICE DEBUG: Error sending emergency supply list via assistant for user: {user.email}, error: {str(result)}")
                
        except Exception as e:
            logger.error(f"EMAIL SERVICE DEBUG: Exception in MealPlanningAssistant send for user: {user.email}, error: {str(e)}")
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'emergency_supply_list',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            
    except Exception as e:
        logger.error(f"EMAIL SERVICE DEBUG: Exception in OpenAI API call: {str(e)}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'emergency_supply_list',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)

@shared_task
@handle_task_failure
def send_system_update_email(subject, message, user_ids=None):
    """
    Send system updates or apology emails to users.
    Args:
        subject: Email subject
        message: HTML message content
        user_ids: Optional list of specific user IDs to send to. If None, sends to all active users.
    """
    from custom_auth.models import CustomUser
    from meals.meal_assistant_implementation import MealPlanningAssistant
    
    try:
        # Get users to send to
        if user_ids:
            users = CustomUser.objects.filter(id__in=user_ids, is_active=True)
        else:
            users = CustomUser.objects.filter(is_active=True)
        
        for user in users:
            try:
                # Skip if user has unsubscribed from emails
                if hasattr(user, 'unsubscribed_from_emails') and user.unsubscribed_from_emails:
                    logger.info(f"User {user.username} has unsubscribed from emails. Skipping system update email.")
                    continue
                    
                # Create personalized context for each user
                account_age_days = (timezone.now().date() - user.date_joined.date()).days
                account_age_years = account_age_days / 365.25
                
                # Get user activity data
                from django.db.models import Count
                from customer_dashboard.models import UserMessage
                message_count = UserMessage.objects.filter(user=user).count()
                
                # Get meal plan data
                meal_plan_count = user.mealplan_set.count() if hasattr(user, 'mealplan_set') else 0
                recent_meal_plans = user.mealplan_set.filter(
                    created_date__gte=timezone.now() - timedelta(days=30)
                ).count() if hasattr(user, 'mealplan_set') else 0
                
                # Extract links from the message if present (simplified approach)
                import re
                links = re.findall(r'href=[\'"]?([^\'" >]+)', message)
                links_str = "\n".join([f"- {link}" for link in links]) if links else "No links in the message."
                
                # Create detailed context message
                enhanced_message = (
                    f"I need to send a system update notification to {user.username}. Here's all the context:\n\n"
                    f"USER CONTEXT:\n"
                    f"- Account age: {account_age_days} days ({account_age_years:.1f} years)\n"
                    f"- Activity level: {'High' if message_count > 100 else 'Medium' if message_count > 20 else 'Low'}\n"
                    f"- Total meal plans: {meal_plan_count}\n"
                    f"- Recent meal plans (last 30 days): {recent_meal_plans}\n\n"
                    f"UPDATE DETAILS:\n"
                    f"- Title: {subject}\n"
                    f"- Content: {message}\n"
                    f"- Relevant links: {links_str}\n\n"
                    f"Please craft a personalized email that conveys this system update. Use an appropriate tone based on how active the user is. "
                    f"For highly active users, emphasize how this update builds on their experience. For less active users, explain how this might "
                    f"make the platform more appealing to them. Include all necessary links from the original message."
                )
                
                # Send via assistant
                result = MealPlanningAssistant.send_notification_via_assistant(
                    user_id=user.id,
                    message_content=enhanced_message,
                    subject=subject
                )
                
                if result.get('status') == 'success':
                    logger.info(f"System update email sent via assistant for: {user.email}")
                else:
                    logger.error(f"Error sending system update email via assistant for: {user.email}, error: {str(result)}")
                    
            except Exception as user_error:
                logger.error(f"Error processing system update for user {user.id}: {user_error}")

    except Exception as e:
        logger.error(f"Error in send_system_update_email: {str(e)}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'send_system_update_email',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        raise

@shared_task
@handle_task_failure
def send_meal_plan_reminder_email():
    """
    Send reminders for unapproved meal plans on Monday for the current week's meal plan
    (which was sent on Saturday night).
    """
    pass
    # from meals.models import MealPlan
    # from customer_dashboard.models import GoalTracking
    
    # # Get current time once
    # current_utc_time = timezone.now()
    # today = current_utc_time.date()
    
    # # Get the date range for this week's meal plan
    # this_week_start = today - timedelta(days=today.weekday())  # Monday
    # this_week_end = this_week_start + timedelta(days=6)  # Sunday
    
    # # Get meal plans that were created on Saturday (2 days ago) and are still unapproved
    # two_days_ago = today - timedelta(days=2)
    # pending_meal_plans = MealPlan.objects.filter(
    #     is_approved=False,
    #     created_date__date=two_days_ago,
    #     week_start_date=this_week_start,
    #     week_end_date=this_week_end,
    #     reminder_sent=False
    # )

    # for meal_plan in pending_meal_plans:
    #     user = meal_plan.user
        
    #     # Skip if user has opted out of emails
    #     if hasattr(user, 'unsubscribed_from_emails') and user.unsubscribed_from_emails:
    #         logger.info(f"User {user.username} has unsubscribed from emails. Skipping meal plan reminder.")
    #         # Mark reminder as sent to avoid future attempts
    #         meal_plan.reminder_sent = True
    #         meal_plan.save()
    #         continue
            
    #     # Skip if not user's Monday
    #     try:
    #         user_timezone = pytz.timezone(user.timezone)
    #         user_time = current_utc_time.astimezone(user_timezone)
    #     except pytz.UnknownTimeZoneError:
    #         logger.error(f"Unknown timezone for user {user.email}: {user.timezone}")
    #         continue

    #     # Check if it's a Monday in the user's time zone
    #     if user_time.weekday() != 0:
    #         continue

    #     try:
    #         # Get user's goals for motivation
    #         goals = GoalTracking.objects.get(user=user)
    #         goal_description = goals.goal_description
            
    #         # Create approval links with meal prep preferences
    #         approval_token = meal_plan.approval_token
    #         base_approval_url = f"{os.getenv('STREAMLIT_URL')}/meal_plans"
            
    #         query_params_daily = urlencode({
    #             'approval_token': approval_token,
    #             'meal_prep_preference': 'daily'
    #         })
    #         query_params_bulk = urlencode({
    #             'approval_token': approval_token,
    #             'meal_prep_preference': 'one_day_prep'
    #         })

    #         # Get meal plan details
    #         meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
    #         meals_by_day = defaultdict(list)
    #         for mpm in meal_plan_meals:
    #             meals_by_day[mpm.day].append({
    #                 'name': mpm.meal.name,
    #                 'type': mpm.meal_type
    #             })
            
    #         # Mark reminder as sent
    #         meal_plan.reminder_sent = True
    #         meal_plan.save()
            
    #         logger.info(f"Monday reminder email sent to n8n for: {user.email}")

    #         # Send via MealPlanningAssistant instead of n8n
    #         try:
    #             from meals.meal_assistant_implementation import MealPlanningAssistant
                
    #             # Get user's health metrics for context if available
    #             user_health_metrics = None
    #             try:
    #                 from customer_dashboard.models import UserHealthMetrics
    #                 latest_metrics = UserHealthMetrics.objects.filter(user=user).order_by('-date_recorded').first()
    #                 if latest_metrics:
    #                     user_health_metrics = {
    #                         'weight': latest_metrics.weight,
    #                         'bmi': latest_metrics.bmi,
    #                         'mood': latest_metrics.mood,
    #                         'energy_level': latest_metrics.energy_level,
    #                     }
    #             except Exception as e:
    #                 logger.error(f"Error retrieving health metrics: {e}")
                
    #             # Build comprehensive message with context
    #             message_content = (
    #                 f"I need to send a meal plan reminder to {user.username} for their meal plan from {this_week_start.strftime('%B %d')} "
    #                 f"to {this_week_end.strftime('%B %d')}. This is a Monday reminder for a meal plan that was created on Saturday but hasn't "
    #                 f"been approved yet. Here's all the context:\n\n"
                    
    #                 f"USER GOALS:\n{goal_description}\n\n"
                    
    #                 f"MEAL PLAN DETAILS:\n"
    #                 f"- Week: {this_week_start.strftime('%B %d, %Y')} to {this_week_end.strftime('%B %d, %Y')}\n"
    #                 f"- Current day in user's timezone: {user_time.strftime('%A, %B %d')}\n"
    #                 f"- Approval links:\n"
    #                 f"  • Daily prep option: {f'{base_approval_url}?{query_params_daily}'}\n"
    #                 f"  • One-day bulk prep option: {f'{base_approval_url}?{query_params_bulk}'}\n\n"
    #             )
                
    #             # Add meals by day
    #             message_content += "MEALS IN THIS PLAN:\n"
    #             for day, meals in meals_by_day.items():
    #                 message_content += f"\n{day}:\n"
    #                 for meal in meals:
    #                     message_content += f"- {meal['type']}: {meal['name']}\n"
                
    #             # Add health metrics if available
    #             if user_health_metrics:
    #                 message_content += "\nUSER HEALTH METRICS:\n"
    #                 for metric, value in user_health_metrics.items():
    #                     if value is not None:
    #                         message_content += f"- {metric}: {value}\n"
                
    #             # Add instructions for the assistant
    #             message_content += (
    #                 f"\nPlease craft a motivational Monday reminder email encouraging the user to approve their meal plan for the week. "
    #                 f"Mention how approving the plan aligns with their health goals. Emphasize that they need to take action today "
    #                 f"to properly prepare for the week ahead. Include both meal prep options (daily vs. bulk) and explain the benefits "
    #                 f"of each approach. The tone should be motivational and supportive, not pushy."
    #             )
                
    #             # Send via assistant
    #             subject = "Start Your Week Right - Your Meal Plan is Waiting!"
                
    #             result = MealPlanningAssistant.send_notification_via_assistant(
    #                 user_id=user.id,
    #                 message_content=message_content,
    #                 subject=subject
    #             )
                
    #             if result.get('status') == 'success':
    #                 # Mark reminder as sent
    #                 meal_plan.reminder_sent = True
    #                 meal_plan.save()
    #                 logger.info(f"Meal plan reminder sent via assistant for: {user.email}")
    #             else:
    #                 logger.error(f"Error sending meal plan reminder via assistant for: {user.email}, error: {str(result)}")
                    
    #         except Exception as e:
    #             logger.error(f"Error sending meal plan reminder via assistant for: {user.email}, error: {str(e)}")
    #             traceback.print_exc()

    #     except Exception as e:
    #         logger.error(f"Error sending reminder email for user {user.email}: {e}")
    #         traceback.print_exc()

# TODO: Set up configuration in n8n
@shared_task
@handle_task_failure
def send_payment_confirmation_email(payment_data):
    """
    Send payment confirmation email to Stripe Connect workers (chefs).
    
    Args:
        payment_data (dict): Dictionary containing payment information:
            - amount (int): Amount in cents
            - currency (str): Currency code (e.g., 'usd')
            - chef_email (str): Email of the chef/worker
            - chef_name (str): Name of the chef/worker
            - order_id (str): Order ID or reference
            - customer_name (str): Name of the customer
            - service_fee (int): Stripe service fee in cents
            - platform_fee (int): Platform fee in cents
            - net_amount (int): Net amount after fees in cents
            - payment_date (str): Payment date
    """
    from custom_auth.models import CustomUser
    from meals.meal_assistant_implementation import MealPlanningAssistant
    from meals.models import ChefMealOrder, Chef
    
    try:
        # Format monetary values
        amount = payment_data['amount'] / 100  # Convert cents to dollars
        service_fee = payment_data['service_fee'] / 100
        platform_fee = payment_data['platform_fee'] / 100
        net_amount = payment_data['net_amount'] / 100
        
        # Get the chef's user account
        chef_user = None
        try:
            chef = Chef.objects.filter(user__email=payment_data['chef_email']).first()
            if chef:
                chef_user = chef.user
            else:
                chef_user = CustomUser.objects.filter(email=payment_data['chef_email']).first()
                
            if not chef_user:
                logger.error(f"Could not find user account for chef email: {payment_data['chef_email']}")
                return
                
            # Check if chef has unsubscribed from emails
            if hasattr(chef_user, 'unsubscribed_from_emails') and chef_user.unsubscribed_from_emails:
                logger.info(f"Chef {chef_user.username} has unsubscribed from emails. Skipping payment confirmation email.")
                return
                
        except Exception as e:
            logger.error(f"Error finding chef user account: {e}")
            return
            
        # Try to get additional context from the order if possible
        additional_context = ""
        try:
            order = ChefMealOrder.objects.filter(id=payment_data['order_id']).select_related('meal_event', 'meal_event__meal').first()
            if order:
                additional_context = (
                    f"ORDER DETAILS:\n"
                    f"- Meal: {order.meal_event.meal.name}\n"
                    f"- Event date: {order.meal_event.date.strftime('%B %d, %Y')}\n"
                    f"- Event time: {order.meal_event.time.strftime('%I:%M %p')}\n"
                    f"- Quantity ordered: {order.quantity}\n"
                    f"- Special instructions: {order.special_instructions if order.special_instructions else 'None'}\n"
                )
        except Exception as e:
            logger.error(f"Error retrieving additional order context: {e}")
            
        # Build detailed message for the assistant
        message_content = (
            f"I need to send a payment confirmation to Chef {payment_data['chef_name']}. Here's all the context:\n\n"
            f"TRANSACTION DETAILS:\n"
            f"- Transaction ID: {payment_data.get('transaction_id', 'Not provided')}\n"
            f"- Order ID: {payment_data['order_id']}\n"
            f"- Payment date: {payment_data['payment_date']}\n"
            f"- Customer: {payment_data['customer_name']}\n\n"
            f"PAYMENT BREAKDOWN:\n"
            f"- Total amount: {amount} {payment_data['currency'].upper()}\n"
            f"- Stripe service fee: {service_fee} {payment_data['currency'].upper()}\n"
            f"- Platform fee: {platform_fee} {payment_data['currency'].upper()}\n"
            f"- Net amount: {net_amount} {payment_data['currency'].upper()}\n\n"
            f"{additional_context}\n\n"
            f"Please craft a professional and clear payment confirmation email that includes all the transaction details "
            f"and explains the breakdown of fees in a transparent manner. Thank the chef for their service and confirm "
            f"that the payment has been processed successfully."
        )
        
        # Send via assistant
        subject = f'Payment Confirmation - Order #{payment_data["order_id"]}'
        
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=chef_user.id,
            message_content=message_content,
            subject=subject
        )
        
        if result.get('status') == 'success':
            logger.info(f"Payment confirmation email sent via assistant for: {payment_data['chef_email']}")
        else:
            logger.error(f"Error sending payment confirmation via assistant for: {payment_data['chef_email']}, error: {str(result)}")
        
    except Exception as e:
        logger.error(f"Error generating or sending payment confirmation email: {e}")
        logger.error(traceback.format_exc())
        raise

@shared_task
@handle_task_failure
def send_refund_notification_email(order_id):
    """
    Send a refund notification email to a customer when their order is refunded.
    
    Args:
        order_id (int): ID of the ChefMealOrder that has been refunded
    """
    from meals.models import ChefMealOrder
    from meals.meal_assistant_implementation import MealPlanningAssistant
    
    try:
        # Get the order
        order = get_object_or_404(ChefMealOrder, id=order_id)
        user = order.customer
        
        # Check if user has unsubscribed from emails
        if hasattr(user, 'unsubscribed_from_emails') and user.unsubscribed_from_emails:
            logger.info(f"User {user.username} has unsubscribed from emails. Skipping refund notification.")
            return
            
        event = order.meal_event
        
        # Format the amount for display
        refund_amount = float(order.price_paid)
        
        # Get formatted date for the refund
        refund_date = timezone.now().strftime("%B %d, %Y")
        
        # Build detailed message for the assistant
        message_content = (
            f"I need to send a refund notification to {user.get_full_name() or user.username}. Here's all the context:\n\n"
            f"REFUND DETAILS:\n"
            f"- Order ID: {order.id}\n"
            f"- Refund amount: {refund_amount} {order.currency if hasattr(order, 'currency') else 'USD'}\n"
            f"- Refund processed on: {refund_date}\n"
            f"- Original payment method: {order.payment_method if hasattr(order, 'payment_method') else 'Card payment'}\n"
            f"- Expected to appear on statement in: 5-10 business days\n\n"
            f"ORDER DETAILS:\n"
            f"- Meal: {event.meal.name}\n"
            f"- Chef: {event.chef.user.get_full_name()}\n"
            f"- Originally scheduled for: {event.date.strftime('%B %d, %Y')} at {event.time.strftime('%I:%M %p')}\n"
            f"- Cancellation reason: {order.cancellation_reason or 'Order was canceled'}\n\n"
            f"Please craft a clear refund confirmation email that reassures the customer their money has been refunded. "
            f"Include all the relevant details about the refund, like the amount, when it was processed, and when they can "
            f"expect to see it on their statement. Briefly mention the original order details for context. "
            f"Use a friendly, professional tone and encourage them to make another order in the future."
        )
        
        # Send via assistant
        subject = f'Your Refund for Order #{order.id} Has Been Processed'
        
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject
        )
        
        if result.get('status') == 'success':
            logger.info(f"Refund notification email sent via assistant for: {user.email}")
        else:
            logger.error(f"Error sending refund notification via assistant for: {user.email}, error: {str(result)}")
            
    except Exception as e:
        logger.error(f"Error generating or sending refund notification email for order {order_id}: {e}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'send_refund_notification_email',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)

@shared_task
@handle_task_failure
def send_order_cancellation_email(order_id):
    """
    Send an order cancellation notification email to a customer.
    
    Args:
        order_id (int): ID of the ChefMealOrder that has been cancelled
    """
    from meals.models import ChefMealOrder
    from meals.meal_assistant_implementation import MealPlanningAssistant
    
    try:
        # Get the order
        order = get_object_or_404(ChefMealOrder, id=order_id)
        user = order.customer
        
        # Check if user has unsubscribed from emails
        if hasattr(user, 'unsubscribed_from_emails') and user.unsubscribed_from_emails:
            logger.info(f"User {user.username} has unsubscribed from emails. Skipping cancellation notification.")
            return
            
        event = order.meal_event
        
        # Format the amount for display if refunded
        order_amount = float(order.price_paid)
        
        # Get formatted dates
        cancellation_date = timezone.now().strftime("%B %d, %Y")
        
        # Determine if this was canceled by the chef or the customer
        canceled_by_chef = 'Event canceled by chef' in order.cancellation_reason if order.cancellation_reason else False
        
        # Try to get recommended alternatives for the user
        alternatives = []
        try:
            from meals.models import ChefMealEvent
            from django.db.models import Q
            
            # Find alternative events for the same meal or by the same chef
            alt_events = ChefMealEvent.objects.filter(
                Q(meal=event.meal) | Q(chef=event.chef),
                date__gte=timezone.now().date(),
                status__in=['scheduled', 'open'],
                orders_count__lt=F('max_orders')
            ).exclude(id=event.id).order_by('date', 'time')[:3]
            
            for alt in alt_events:
                alternatives.append({
                    'meal_name': alt.meal.name,
                    'chef_name': alt.chef.user.get_full_name() or alt.chef.user.username,
                    'date': alt.date.strftime("%B %d, %Y"),
                    'time': alt.time.strftime("%I:%M %p"),
                    'price': float(alt.current_price),
                })
        except Exception as e:
            logger.error(f"Error finding alternatives for canceled order: {e}")
        
        # Build detailed message for the assistant
        message_content = (
            f"I need to send an order cancellation notice to {user.get_full_name() or user.username}. Here's all the context:\n\n"
            f"ORDER DETAILS:\n"
            f"- Order ID: {order.id}\n"
            f"- Meal: {event.meal.name}\n"
            f"- Chef: {event.chef.user.get_full_name()}\n"
            f"- Originally scheduled for: {event.date.strftime('%B %d, %Y')} at {event.time.strftime('%I:%M %p')}\n"
            f"- Amount paid: {order_amount} {order.currency if hasattr(order, 'currency') else 'USD'}\n"
            f"- Cancellation date: {cancellation_date}\n"
            f"- Cancellation reason: {order.cancellation_reason or 'No specific reason provided'}\n"
            f"- Canceled by: {'Chef' if canceled_by_chef else 'Customer'}\n"
            f"- Refund status: {order.refund_status if hasattr(order, 'refund_status') else 'Unknown'}\n\n"
        )
        
        if alternatives:
            message_content += "ALTERNATIVE OPTIONS:\n"
            for alt in alternatives:
                message_content += (
                    f"- {alt['meal_name']} by Chef {alt['chef_name']}\n"
                    f"  Date: {alt['date']} at {alt['time']}\n"
                    f"  Price: ${alt['price']:.2f}\n\n"
                )
        else:
            message_content += "No alternative meal events are currently available.\n\n"
            
        message_content += (
            f"Please craft an empathetic order cancellation email that acknowledges the customer's disappointment "
            f"but maintains a positive tone. Explain the cancellation clearly, including the reason if one was provided. "
            f"If the order was canceled by the chef, offer a sincere apology. "
            f"Clearly communicate the refund status if available. "
            f"If alternatives are available, suggest them as options the customer might consider. "
            f"End with an upbeat note encouraging them to explore other meal options on the platform."
        )
        
        # Send via assistant
        subject = f'Your Order #{order.id} Has Been Cancelled'
        
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject
        )
        
        if result.get('status') == 'success':
            logger.info(f"Order cancellation email sent via assistant for: {user.email}")
        else:
            logger.error(f"Error sending order cancellation via assistant for: {user.email}, error: {str(result)}")
            
    except Exception as e:
        logger.error(f"Error generating or sending order cancellation email for order {order_id}: {e}")
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'send_order_cancellation_email',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)