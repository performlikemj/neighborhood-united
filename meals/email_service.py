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
from zoneinfo import ZoneInfo
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
from meals.pydantic_models import ShoppingList as ShoppingListSchema
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

# Approval emails removed; we keep other email tasks intact.

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

    # Determine today's date in the user's timezone
    try:
        user_tz = ZoneInfo(user.timezone) if getattr(user, 'timezone', None) else ZoneInfo("UTC")
    except Exception:
        user_tz = ZoneInfo("UTC")
    today_local = timezone.now().astimezone(user_tz).date()

    # Compute which MealPlanMeals are in the future (or today) relative to user's local date
    # Build a mapping of day name to date based on the plan's week_start_date
    from datetime import timedelta as _td
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    week_start_date = meal_plan.week_start_date
    day_to_date_map = {day_names[i]: (week_start_date + _td(days=i)) for i in range(7)}

    # Filter serializer meals list to only include today or future dates
    original_meals = meal_plan_data.get('meals', []) or []
    filtered_meals = [
        m for m in original_meals
        if day_to_date_map.get(m.get('day')) is None or day_to_date_map[m.get('day')] >= today_local
    ]

    # If the entire plan is in the past, skip generation to avoid wasting resources
    if not filtered_meals:
        logger.info(f"Shopping list skipped for MealPlan ID {meal_plan_id}: all meals are in the past (today={today_local}, plan={meal_plan.week_start_date}..{meal_plan.week_end_date}).")
        return

    # Overwrite meals in the serialized structure with the filtered subset
    meal_plan_data['meals'] = filtered_meals

    # Also derive the included Meal IDs to scope substitution logic below
    included_meal_ids = {m.get('meal', {}).get('id') for m in filtered_meals if isinstance(m.get('meal'), dict)}

    # Retrieve the user's preferred serving size
    try:
        household_member_count = user.household_member_count
    except Exception as e:
        logger.error(f"Error retrieving household member count for user {user.id}: {e}")
        household_member_count = 1

    # Collect ingredient substitution information only for included meals in the plan
    substitution_info = []
    chef_meals_present = False
    # Use related through model to retain day/date filtering
    try:
        from meals.models import MealPlanMeal as _MPM
        mpm_qs = _MPM.objects.filter(meal_plan=meal_plan).select_related('meal')
        # Apply the same date filter
        mpm_in_scope = []
        for mpm in mpm_qs:
            # Prefer explicit meal_date if present; else compute from day
            m_date = getattr(mpm, 'meal_date', None)
            if not m_date:
                m_date = day_to_date_map.get(mpm.day)
            if m_date is not None and m_date < today_local:
                continue
            mpm_in_scope.append(mpm)
        meal_plan_meals = [mpm.meal for mpm in mpm_in_scope]
    except Exception:
        # Fallback: filter by included_meal_ids from serializer
        meal_plan_meals = [m for m in meal_plan.meal.all() if (not included_meal_ids) or (m.id in included_meal_ids)]
    
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
                model="o4-mini-2025-04-16",
                input=[
                    {
                        "role": "developer",
                        "content": (
                            "You are a helpful assistant that generates shopping lists in JSON format.\n"
                            "If a meal contains a composed_dishes bundle (user-generated multi-dish meal), ensure the shopping list fully covers ingredients for all dishes in the bundle.\n"
                            "For such bundles, include the dish name in the 'notes' field for each relevant item (e.g., 'For baby puree' or 'Vegan dish').\n"
                            "Respect substitutions for non-chef meals.\n"
                            "When available, prefer structured meal_dishes (MealDish rows) over composed_dishes JSON.\n"
                            "Return one entry per unique ingredient and unit; if multiple meals require the same ingredient with the same unit, combine their quantities and list all meal names in `meal_names`.\n"
                        )
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

    # --- helpers for normalization/deduplication ---
    def _normalize_unit(u: str) -> str:
        if not u:
            return ''
        unit = str(u).strip().lower()
        # remove redundant words
        unit = unit.replace(' units', '').replace(' unit', '')
        # collapse duplicates like "slices slices"
        parts = unit.split()
        if len(parts) == 2 and parts[0] == parts[1]:
            unit = parts[0]
        # standardize common units
        mapping = {
            'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbs': 'tbsp', 'tbsp': 'tbsp',
            'teaspoon': 'tsp', 'teaspoons': 'tsp', 'tsp': 'tsp',
            'grams': 'g', 'gram': 'g', 'g': 'g',
            'kilogram': 'kg', 'kilograms': 'kg', 'kg': 'kg',
            'milliliter': 'ml', 'milliliters': 'ml', 'ml': 'ml',
            'liter': 'l', 'liters': 'l', 'l': 'l',
            'pieces': '', 'piece': '', 'pcs': '',
            'ounce': 'oz', 'ounces': 'oz', 'oz': 'oz',
            'pound': 'lb', 'pounds': 'lb', 'lb': 'lb', 'lbs': 'lb',
            'dozen': 'dozen',
        }
        unit = mapping.get(unit, unit)
        return unit

    def _convert_quantity_to_canonical(qty: float, unit_norm: str):
        """
        Convert quantity/unit to canonical small units where possible.
        Weight → grams (g); Volume → milliliters (ml); dozen → pieces.
        Returns (quantity, unit).
        """
        if qty is None:
            return qty, unit_norm
        try:
            if unit_norm == 'kg':
                return qty * 1000.0, 'g'
            if unit_norm == 'l':
                return qty * 1000.0, 'ml'
            if unit_norm == 'lb':
                return qty * 453.592, 'g'
            if unit_norm == 'oz':
                return qty * 28.3495, 'g'
            if unit_norm == 'dozen':
                return qty * 12.0, 'pieces'
        except Exception:
            return qty, unit_norm
        return qty, unit_norm

    def _format_for_measurement_system(qty: float, unit_norm: str, measurement_system: str):
        """
        Convert canonical qty/unit (g, ml, or other normalized units) into a user‑friendly
        representation based on the user's measurement system preference.
        - For METRIC: prefer kg for >= 1000 g; l for >= 1000 ml.
        - For US: convert grams to oz/lb (>= 16 oz -> lb), ml to cups (>= 240 ml) else fl oz.
        Other units are returned unchanged.
        Returns (display_qty: float|str|None, display_unit: str)
        """
        system = (measurement_system or 'METRIC').upper()
        try:
            if qty is None:
                return qty, unit_norm

            # Weight handling
            if unit_norm == 'g':
                if system == 'US':
                    oz = qty / 28.3495
                    if oz >= 16.0:
                        lb = oz / 16.0
                        return lb, 'lb'
                    return oz, 'oz'
                # metric
                if qty >= 1000.0:
                    return qty / 1000.0, 'kg'
                return qty, 'g'

            # Volume handling
            if unit_norm == 'ml':
                if system == 'US':
                    # Prefer cups for larger volumes, fl oz for small
                    if qty >= 240.0:
                        cups = qty / 240.0
                        return cups, 'cups'
                    fl_oz = qty / 29.5735
                    return fl_oz, 'fl oz'
                # metric
                if qty >= 1000.0:
                    return qty / 1000.0, 'l'
                return qty, 'ml'

            # leave everything else as-is
            return qty, unit_norm
        except Exception:
            return qty, unit_norm

    def _clean_note(note: str) -> str:
        if not note:
            return ''
        import re
        s = re.sub(r'\([^)]*\)', '', str(note)).strip()
        # shorten overly long notes
        if len(s) > 140:
            s = s[:137].rstrip() + '...'
        return s

    for item in shopping_list_dict.get("items", []):
        logger.info(f"Shopping list item: {item}")
        category = item.get("category", "Miscellaneous")
        ingredient = item.get("ingredient")
        quantity_value = item.get("quantity", "")
        unit = item.get("unit", "")
        meal_names = item.get("meal_names", [])
        notes = item.get("notes", "")

        # Handle numeric quantities (schema enforces float), but remain defensive
        quantity = None
        try:
            if isinstance(quantity_value, (int, float)):
                quantity = float(quantity_value)
            elif isinstance(quantity_value, str):
                qs = quantity_value.strip()
                if '/' in qs and re.match(r'^\s*\d+\s*/\s*\d+\s*$', qs):
                    numerator, denominator = qs.split('/')
                    quantity = float(numerator) / float(denominator)
                else:
                    quantity = float(re.sub(r'[^0-9\./]', '', qs)) if re.search(r'[0-9]', qs) else None
        except Exception:
            quantity = None
        if quantity is None:
            logger.info(f"Non-numeric quantity '{quantity_value}' for ingredient '{ingredient}'")

        unit_norm = _normalize_unit(unit)
        # Convert to canonical units if applicable
        if quantity is not None:
            quantity, unit_norm = _convert_quantity_to_canonical(quantity, unit_norm)

        if quantity is not None:
            existing = categorized_items[category].get(ingredient)
            # If another unit was already stored and differs, split into a variant key
            if existing and existing['unit'] and existing['unit'] != unit_norm:
                ingredient_variant = f"{ingredient} ({unit_norm})"
                categorized_items[category][ingredient_variant]['quantity'] += quantity
                categorized_items[category][ingredient_variant]['unit'] = unit_norm
            else:
                categorized_items[category][ingredient]['quantity'] += quantity
                categorized_items[category][ingredient]['unit'] = unit_norm
        else:
            # For e.g. "To taste"
            if not categorized_items[category][ingredient]['unit']:
                categorized_items[category][ingredient]['quantity'] = str(quantity_value)
                categorized_items[category][ingredient]['unit'] = unit_norm

        # Append any relevant notes
        if notes and 'none' not in notes.lower():
            cleaned = _clean_note(notes)
            if cleaned:
                note_list = categorized_items[category][ingredient]['notes']
                # Avoid dupes (case-insensitive)
                if cleaned.lower() not in [n.lower() for n in note_list]:
                    note_list.append(cleaned)
                # Cap at 2 concise notes
                if len(note_list) > 2:
                    categorized_items[category][ingredient]['notes'] = note_list[:2]

    # Build the final message for the assistant (regular shopping list only)
    try:
        from meals.meal_assistant_implementation import MealPlanningAssistant

        # (Removed emergency supply unit conversion and pantry preface — not applicable to shopping list email)

        # Keep the assistant text minimal; the template renders tables from structured context
        message_content = (
            f"Please send a professional weekly shopping list for {user_name} "
            f"({meal_plan.week_start_date.strftime('%B %d')} – {meal_plan.week_end_date.strftime('%B %d')}). "
            f"Use the structured tables provided; avoid meal-by-meal commentary."
        )

        # Build structured tables for template rendering, honoring user's measurement preference
        shopping_tables = []
        if categorized_items:
            try:
                measurement_system = getattr(user, 'measurement_system', 'METRIC')
            except Exception:
                measurement_system = 'METRIC'
            for category, items_in_category in categorized_items.items():
                table_items = []
                for ingredient, details in items_in_category.items():
                    qty = details.get('quantity')
                    unit = details.get('unit')
                    # Convert canonical qty/unit to user's display system
                    if isinstance(qty, (int, float)):
                        qty_disp, unit_disp = _format_for_measurement_system(float(qty), str(unit or ''), measurement_system)
                    else:
                        qty_disp, unit_disp = qty, _normalize_unit(unit)
                    notes_list = details.get('notes', []) or []
                    # Normalize quantity to a friendly string
                    if isinstance(qty_disp, (int, float)):
                        qf = float(qty_disp)
                        qty_str = (f"{qf:.2f}".rstrip('0').rstrip('.') if qf % 1 != 0 else f"{int(qf)}")
                    else:
                        qty_str = str(qty_disp)
                    # Build a concise, normalized row
                    table_items.append({
                        'ingredient': ingredient,
                        'quantity': qty_str,
                        'unit': _normalize_unit(unit_disp),
                        'notes': '; '.join([n for n in (notes_list[:2] if isinstance(notes_list, list) else [notes_list]) if n]) or '',
                    })
                shopping_tables.append({'category': category, 'items': table_items})

        subject = f"Your Shopping List for {meal_plan.week_start_date.strftime('%b %d')} - {meal_plan.week_end_date.strftime('%b %d')}"

        # Generate Instacart link for US/CA users and include in context
        instacart_url = None
        try:
            user_country_code = None
            try:
                if hasattr(user, 'address') and user.address and getattr(user.address, 'country', None):
                    # Some Address.country are stored as codes, some as Country object with .code – handle both
                    country_attr = user.address.country
                    user_country_code = getattr(country_attr, 'code', None) or str(country_attr)
                    user_country_code = str(user_country_code).upper() if user_country_code else None
            except Exception:
                user_country_code = None

            if user_country_code in ("US", "CA"):
                postal_code = None
                try:
                    postal_code = getattr(user.address, 'input_postalcode', None) or getattr(user.address, 'postalcode', None)
                except Exception:
                    postal_code = None
                from meals.instacart_service import generate_instacart_link as _generate_instacart_link
                gen_result = _generate_instacart_link(user.id, meal_plan.id, postal_code)
                if gen_result and gen_result.get('status') == 'success' and gen_result.get('instacart_url'):
                    instacart_url = gen_result.get('instacart_url')
        except Exception as _insta_err:
            logger.warning(f"Instacart link generation skipped or failed for user {user.id}: {_insta_err}")

        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject,
            template_key='shopping_list',
            template_context={
                'has_categories': bool(categorized_items),
                'household_member_count': household_member_count,
                'week_start': meal_plan.week_start_date.strftime('%B %d, %Y'),
                'week_end': meal_plan.week_end_date.strftime('%B %d, %Y'),
                'shopping_tables': shopping_tables,
                'instacart_url': instacart_url,
            }
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
        user_timezone = ZoneInfo(user.timezone if getattr(user, 'timezone', None) else 'UTC')
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
        ""
        "• Encouraging, business-casual tone.\n"
        f"• Respond ONLY in {_get_language_name(user.preferred_language)}."
    )

    try:
        resp = get_openai_client().responses.create(
            model="o4-mini-2025-04-16",
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
            model="o4-mini-2025-04-16",
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

        # Always validate with Pydantic schema. On failure: send error email and emit N8N traceback.
        emergency_list: list = []
        notes: str = ""
        try:
            from meals.pydantic_models import EmergencySupplyList as _EmergencySupplyList
            parsed = _EmergencySupplyList.model_validate_json(gpt_output_str)
            # Convert to plain dicts for template safety
            emergency_list = [
                {
                    'item_name': item.item_name,
                    'quantity_to_buy': item.quantity_to_buy,
                    'unit': item.unit,
                    'notes': item.notes,
                }
                for item in parsed.emergency_list
            ]
            notes = parsed.notes or ""
        except Exception as e_validate:
            logger.error(f"EMAIL SERVICE DEBUG: EmergencySupplyList schema validation failed: {e_validate}")
            # n8n traceback with raw model output for diagnostics
            try:
                requests.post(os.getenv('N8N_TRACEBACK_URL'), json={
                    'error': f'Pydantic validation failed: {str(e_validate)}',
                    'source': 'emergency_supply_list',
                    'raw_output': gpt_output_str,
                    'user_id': user.id,
                })
            except Exception:
                pass

            # Send a concise error email to the user and exit early
            try:
                from meals.meal_assistant_implementation import MealPlanningAssistant
                error_message = (
                    "We hit a snag generating your emergency supply plan just now. "
                    "Our system has logged the error and we’ll retry shortly. If this persists, please reply to this email."
                )
                MealPlanningAssistant.send_notification_via_assistant(
                    user_id=user.id,
                    message_content=error_message,
                    subject="Emergency Supply Plan – Temporary Error",
                    template_key=None,
                    template_context=None,
                )
            except Exception as _e_send:
                logger.error(f"EMAIL SERVICE DEBUG: Failed to send validation error email: {_e_send}")
            return  # Abort normal flow

        # Convert emergency_list units to user's preferred measurement system for display
        try:
            measurement_system = getattr(user, 'measurement_system', 'METRIC')
        except Exception:
            measurement_system = 'METRIC'

        def _es_normalize_unit(u: str) -> str:
            if not u:
                return ''
            unit = str(u).strip().lower()
            mapping = {
                'grams': 'g', 'gram': 'g', 'g': 'g',
                'kilogram': 'kg', 'kilograms': 'kg', 'kg': 'kg',
                'milliliter': 'ml', 'milliliters': 'ml', 'ml': 'ml',
                'liter': 'l', 'liters': 'l', 'l': 'l',
                'ounce': 'oz', 'ounces': 'oz', 'oz': 'oz',
                'pound': 'lb', 'pounds': 'lb', 'lb': 'lb', 'lbs': 'lb',
                'fluid ounce': 'fl oz', 'fluid ounces': 'fl oz', 'floz': 'fl oz', 'fl oz': 'fl oz',
                'cup': 'cups', 'cups': 'cups',
                'piece': 'pieces', 'pieces': 'pieces', 'pcs': 'pieces',
                'can': 'cans', 'cans': 'cans',
                'bottle': 'bottles', 'bottles': 'bottles',
                'packet': 'packets', 'packets': 'packets',
            }
            return mapping.get(unit, unit)

        def _es_parse_qty(val):
            try:
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                import re
                if '/' in s and re.match(r'^\s*\d+\s*/\s*\d+\s*$', s):
                    a, b = s.split('/')
                    return float(a) / float(b)
                m = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)', s)
                if m:
                    return float(m.group(1))
            except Exception:
                pass
            return None

        def _es_to_canonical(qty: float, unit_norm: str):
            if qty is None:
                return qty, unit_norm
            try:
                if unit_norm == 'kg':
                    return qty * 1000.0, 'g'
                if unit_norm == 'l':
                    return qty * 1000.0, 'ml'
                if unit_norm == 'lb':
                    return qty * 453.592, 'g'
                if unit_norm == 'oz':
                    return qty * 28.3495, 'g'
                if unit_norm == 'fl oz':
                    return qty * 29.5735, 'ml'
                if unit_norm == 'cups':
                    return qty * 240.0, 'ml'
            except Exception:
                return qty, unit_norm
            return qty, unit_norm

        def _es_format_for_system(qty: float, unit_norm: str):
            sys = (measurement_system or 'METRIC').upper()
            try:
                if qty is None:
                    return qty, unit_norm
                if unit_norm == 'g':
                    if sys == 'US':
                        oz = qty / 28.3495
                        if oz >= 16.0:
                            return oz / 16.0, 'lb'
                        return oz, 'oz'
                    return (qty / 1000.0, 'kg') if qty >= 1000.0 else (qty, 'g')
                if unit_norm == 'ml':
                    if sys == 'US':
                        if qty >= 240.0:
                            return qty / 240.0, 'cups'
                        return qty / 29.5735, 'fl oz'
                    return (qty / 1000.0, 'l') if qty >= 1000.0 else (qty, 'ml')
                return qty, unit_norm
            except Exception:
                return qty, unit_norm

        converted_emergency_list = []
        for it in emergency_list:
            name = it.get('item_name')
            qty_raw = it.get('quantity_to_buy')
            unit_raw = it.get('unit')
            notes_item = it.get('notes')
            unit_norm = _es_normalize_unit(unit_raw)
            qty_val = _es_parse_qty(qty_raw)
            if qty_val is not None and unit_norm in ('g', 'kg', 'ml', 'l', 'oz', 'lb', 'fl oz', 'cups'):
                c_qty, c_unit = _es_to_canonical(qty_val, unit_norm)
                d_qty, d_unit = _es_format_for_system(c_qty, c_unit)
                if isinstance(d_qty, (int, float)):
                    dq = float(d_qty)
                    qty_out = (f"{dq:.2f}".rstrip('0').rstrip('.') if dq % 1 != 0 else f"{int(dq)}")
                else:
                    qty_out = str(d_qty)
                unit_out = d_unit
            else:
                qty_out = str(qty_raw) if qty_raw is not None else ''
                unit_out = unit_raw or ''
            converted_emergency_list.append({
                'item_name': name,
                'quantity_to_buy': qty_out,
                'unit': unit_out,
                'notes': notes_item or ''
            })

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
            if converted_emergency_list:
                message_content += "RECOMMENDED EMERGENCY SUPPLIES TO PURCHASE:\n"
                for item in converted_emergency_list:
                    try:
                        item_name = item.get('item_name', 'Unknown item')
                        quantity = item.get('quantity_to_buy', '')
                        unit = item.get('unit', '')
                        notes = item.get('notes', '')
                            
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
            
            # Log the number of emergency items gathered for template rendering
            try:
                logger.info(f"EMAIL SERVICE DEBUG: Emergency list items count: {len(converted_emergency_list)}")
            except Exception:
                pass

            # Add emergency preparedness tips and explicit constraints
            message_content += (
                "Write a concise, helpful email about emergency food preparedness that includes ONLY the emergency "
                "supplies the user should purchase and practical storage/rotation tips. Do not include or mention any "
                "weekly or regular shopping lists. Acknowledge allergies and explain how the recommended items account "
                "for those restrictions. Keep the tone informative and supportive, not alarmist."
            )
            
            subject = f"Your Emergency Supply List for {days_of_supply} Days"
            
            result = MealPlanningAssistant.send_notification_via_assistant(
                user_id=user.id,
                message_content=message_content,
                subject=subject,
                template_key='emergency_supply',
                template_context={
                    # Provide the flat list parsed from the schema for template rendering
                    'emergency_list': converted_emergency_list,
                }
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
def send_system_update_email(subject, message, user_ids=None, template_key='system_update', template_context=None):
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
                    subject=subject,
                    template_key=template_key or 'system_update',
                    template_context=template_context or None
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
            subject=subject,
            template_key='payment_confirmation'
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
            subject=subject,
            template_key='refund_notification'
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
            subject=subject,
            template_key='order_cancellation'
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
