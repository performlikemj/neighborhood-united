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
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
from pydantic import ValidationError
from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal, MealPlanInstruction
from meals.pydantic_models import MealPlanApprovalEmailSchema, ShoppingList as ShoppingListSchema
from meals.pantry_management import get_user_pantry_items, get_expiring_pantry_items, determine_items_to_replenish
from meals.meal_embedding import serialize_data
from meals.serializers import MealPlanSerializer
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, UserSummary, UserDailySummary
from shared.utils import generate_user_context
from meals.meal_plan_service import is_chef_meal
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

@shared_task
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

            # **Check if the user has opted in to receive meal plan emails**
            if not user.email_meal_plan_saved:
                logger.info(f"User {user.username} has opted out of meal plan emails.")
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
            preferred_language = user.preferred_language
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
                "meal_obj": meal.meal  # Add the actual meal object
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

        # Call OpenAI to generate the email content
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "developer",
                        "content": "You are a helpful assistant that generates meal plan approval emails."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate an email in {preferred_language}, given what you know about the user: {user_context}, that includes the following:\n\n"
                            f"1. Greet the user by their name: {user_name}.\n"
                            f"2. Inform them that their meal plan for the week {meal_plan.week_start_date} to {meal_plan.week_end_date} has been created.\n"
                            f"3. Include a well-formatted and high-level summary of the following list of meals in their plan:\n{meals_list}. Make the summary enticing and engaging with newlines where necessary to avoid a cramped description."
                        )
                    }
                ],
                #store=True,
                #metadata={'tag': 'meal_plan_approval_email'},
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'approval_email',
                        'schema': MealPlanApprovalEmailSchema.model_json_schema()
                    }
                }
            )

            response_content = response.output_text
            email_data_dict = json.loads(response_content)

            # Modify summary_text to support bold text and newlines
            if 'summary_text' in email_data_dict:
                summary_text = email_data_dict['summary_text']
                # Replace **text** with <strong>text</strong>
                summary_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', summary_text)
                # Replace newlines with <br>
                summary_text = summary_text.replace('\n', '<br>')
                email_data_dict['summary_text'] = summary_text

            email_model = MealPlanApprovalEmailSchema(**email_data_dict)

            # Generate the profile URL
            profile_url = f"{os.getenv('STREAMLIT_URL')}/profile"

            # --- Replace Jinja2 with Django Template Rendering ---
            context = {
                'user_name': user_name,
                'meal_plan_week_start': meal_plan.week_start_date.strftime('%B %d, %Y'), # Example formatting
                'meal_plan_week_end': meal_plan.week_end_date.strftime('%B %d, %Y'),   # Example formatting
                'approval_link_daily': approval_link_daily,
                'approval_link_one_day': approval_link_one_day,
                'meals_list': meals_list,
                'summary_text': email_model.summary_text, # Use summary from model
                'profile_url': profile_url,
            }

            # Render the template using Django's engine
            # Note: The path 'meals/meal_plan_email.html' should be relative to a directory
            # listed in TEMPLATES['DIRS'] or within an app's 'templates' directory.
            email_body_html = render_to_string('meals/meal_plan_email.html', context)
            # --- End of replacement ---

            email_data = {
                'subject': f'Approve Your Meal Plan for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
                'html_message': email_body_html,
                'to': user_email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
                'from': 'support@sautai.com',
            }

            try:
                logger.debug(f"Sending approval email to n8n for: {user_email}")
                n8n_url = os.getenv("N8N_GENERATE_APPROVAL_EMAIL_URL")
                response = requests.post(n8n_url, json=email_data)
                response.raise_for_status() # Check for HTTP errors from n8n
                logger.info(f"Approval email successfully sent to n8n for: {user_email}")
                with transaction.atomic():
                    meal_plan.approval_email_sent = True
                    meal_plan.save()
            except Exception as e:
                logger.error(f"Error sending approval email to n8n for: {user_email}, error: {str(e)}")
                traceback.print_exc()

        except Exception as e:
            logger.error(f"Error generating or sending approval email: {e}")
            traceback.print_exc()
            # Optionally, re-raise the exception if needed
            # raise

    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        # Handle exception as needed

@shared_task
def generate_shopping_list(meal_plan_id):
    from django.db.models import Sum
    from meals.models import MealPlan, ShoppingList as ShoppingListModel, MealPlanMealPantryUsage, PantryItem, MealAllergenSafety
    # Import is_chef_meal locally to avoid circular imports
    from meals.meal_plan_service import is_chef_meal
    
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
        preferred_serving_size = user.preferred_servings
    except Exception as e:
        logger.error(f"Error retrieving preferred serving size for user {user.id}: {e}")
        preferred_serving_size = 1

    # Collect all ingredient substitution information from the meal plan
    substitution_info = []
    chef_meals_present = False
    meal_plan_meals = meal_plan.meal.all()
    
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

    # Retrieve emergency supply goal
    try:
        emergency_supply_goal = user.emergency_supply_goal
    except Exception as e:
        logger.error(f"Error retrieving emergency supply goal for user {user.id}: {e}")
        emergency_supply_goal = 0

    # Determine items to replenish
    try:
        items_to_replenish = determine_items_to_replenish(user)
    except Exception as e:
        logger.error(f"Error determining items to replenish for user {user.id}: {e}")
        items_to_replenish = []

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
            substitution_str = ""
            if substitution_info:
                substitution_str = "Ingredient substitution information:\n"
                for sub in substitution_info:
                    substitution_str += f"- In {sub['meal_name']}, replace {sub['original_ingredient']} with {', '.join(sub['substitutes'])}\n"
            
            # Add chef meal note if needed
            chef_note = ""
            if chef_meals_present:
                chef_note = "IMPORTANT: Some meals in this plan are chef-created and must be prepared exactly as specified. Do not suggest substitutions for chef-created meals. Include all ingredients for chef meals without alternatives."
            
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "developer",
                        "content": "You are a helpful assistant that generates shopping lists in JSON format."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Answering in the user's preferred language: {user_info.get('preferred_language', 'English')},"
                            f"Generate a shopping list based on the following meals: {json.dumps(user_data_json)}. "
                            f"The user information is as follows: {user_context}. "
                            f"Bridging leftover info if user follows their meal plan: {bridging_leftover_str}. "
                            f"The leftover amounts are calculated based on the user's pantry items and the meals they plan to prepare. "
                            f"Based on the leftover amounts in relation to the required servings, the user may not need to purchase additional items. "
                            f"The user has the following items in their pantry: {', '.join(user_pantry_items)}. "
                            f"The user has to serve {preferred_serving_size} people per meal. Please adjust the quantities accordingly. "
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

    # Format the HTML output
    project_dir = settings.BASE_DIR
    env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
    template = env.get_template('meals/shopping_list_email.html')

    # Prepare your context for rendering
    context = {
        'user_name': user_name,
        'meal_plan_week_start': meal_plan.week_start_date,
        'meal_plan_week_end': meal_plan.week_end_date,
        'categorized_items': categorized_items,
        'profile_url': f"{os.getenv('STREAMLIT_URL')}/profile",  # or however you define it
    }

    # Render the template
    email_body_html = template.render(**context)

    # Then create email_data just like you do in your existing code
    email_data = {
        'subject': f'Your Curated Shopping List for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
        'message': email_body_html,  # or 'html_message' if you want
        'to': user_email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
        'from': 'support@sautai.com',
    }

    # Then send data to n8n (or wherever) just as before
    try:
        logger.info(f"Sending shopping list to {user_email} => {email_data}")
        n8n_url = os.getenv("N8N_GENERATE_SHOPPING_LIST_URL")
        requests.post(n8n_url, json=email_data)
        logger.info(f"Shopping list sent to n8n for: {user_email}")
    except Exception as e:
        logger.error(f"Error sending shopping list to n8n for: {user_email}, error: {str(e)}")

@shared_task
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
    
    print(f"Generating user summary for user {user_id}")
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
        print(f"Data unchanged for user {user_id} on {summary_date}, skipping generation")
        return
    
    # Update hash and status
    summary.data_hash = data_hash
    summary.status = UserDailySummary.PENDING
    summary.save(update_fields=["data_hash", "status"])

    lang_map = {
        "en": "English",
        "jp": "Japanese",
        "es": "Spanish",
        "fr": "French",
    }
    target_lang = lang_map.get((user.preferred_language or "").lower(), "English")

    system_prompt = (
        "You are a friendly, motivating wellness assistant named MJ.\n"
        f"Write a daily summary for the user **in {target_lang}**.\n"
        f"• Focus on {time_period_description}\n"
        "• Warm greeting with the user's first name if available.\n"
        "• Overview ≤ 5 sentences.\n"
        "• Sections: 1) Goals & Status, 2) Health Metrics trends, 3) Calorie-Intake insights.\n"
        "• Omit any empty section.\n"
        "• If meal_plan_needs_approval is true, add one gentle reminder at the end.\n"
        "• Encouraging, business-casual tone.\n"
        f"• Respond ONLY in {target_lang}."
    )

    client = OpenAI(api_key=settings.OPENAI_KEY)

    try:
        resp = client.responses.create(
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
    except Exception as exc:
        summary.status = UserDailySummary.ERROR
        summary.summary = f"Unhandled error: {exc}"
        
        legacy_summary.status = "error"
        legacy_summary.summary = f"Unhandled error: {exc}"

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
def generate_emergency_supply_list(user_id):
    """
    Creates or updates an emergency supply list for the user,
    ensuring they have enough non-perishable items for `emergency_supply_goal` days * `preferred_servings`.
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
        logger.info(f"User {user.username} has no emergency_supply_goal set. Skipping.")
        return

    days_of_supply = user.emergency_supply_goal
    servings_per_meal = user.preferred_servings or 1
    total_serving_days = days_of_supply * servings_per_meal

    logger.info(
        f"Generating emergency supply list for {user.username}, aiming for "
        f"{days_of_supply} days * {servings_per_meal} people per meal = {total_serving_days} total serving-days."
    )

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
            logger.debug(f"Excluding {pi.item_name} from {user.username}'s emergency supply (potential allergen).")

    # 3) Summarize the user's safe pantry items
    user_emergency_pantry_summary = []
    for pi in safe_pantry_items:
        weight_each = float(pi.weight_per_unit or 1.0)
        total_capacity = pi.quantity * weight_each
        user_emergency_pantry_summary.append({
            "item_name": pi.item_name,
            "item_type": pi.item_type,
            "unit": pi.weight_unit,
            "quantity_available": pi.quantity,
            "weight_per_unit": weight_each,
            "total_capacity_in_unit": total_capacity
        })

    # 4) GPT call
    user_context = generate_user_context(user) or 'No additional user context.'
    user_allergies = get_user_allergies(user)
    pantry_summary_json = json.dumps(user_emergency_pantry_summary)

    try:
        from meals.pydantic_models import EmergencySupplyList
        response = client.responses.create(
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
                        f"covering {servings_per_meal} people per meal, i.e. a total of {total_serving_days} 'servings.'\n"
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
            logger.warning("GPT output was not valid JSON; storing raw text.")
            emergency_list = []
            notes = f"GPT returned non-JSON output: {gpt_output_str}"

        # Format the safe items into a simpler structure for the template
        safe_items_data = [
            {
                "item_name": pi.item_name,
                "quantity_available": pi.quantity,
                "unit": pi.weight_unit or "",
                "notes": pi.notes or "",
            }
            for pi in safe_pantry_items
        ]

        # 5) Render + send
        project_dir = settings.BASE_DIR
        env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
        template = env.get_template('meals/emergency_supply_email.html')

        email_body_html = template.render(
            user_name=user.username,
            days_of_supply=days_of_supply,
            servings_per_meal=servings_per_meal,
            safe_pantry_items=safe_items_data,
            emergency_list=emergency_list,
            notes=notes,
            profile_url=f"{os.getenv('STREAMLIT_URL')}/profile"
        )

        email_data = {
            "subject": f"Emergency Supply List for {days_of_supply} Days",
            "message": email_body_html,
            "to": user.email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
            "from": "support@sautai.com",
        }

        try:
            n8n_url = os.getenv("N8N_GENERATE_EMERGENCY_LIST_URL")
            if n8n_url:
                requests.post(n8n_url, json=email_data)
                logger.info(f"Sent emergency supply list to n8n for user {user.username}")
            else:
                logger.info("No N8N_GENERATE_EMERGENCY_LIST_URL found; skipping external send.")
        except Exception as e:
            logger.error(f"Error sending emergency supply list to n8n: {str(e)}")

    except Exception as e:
        logger.error(f"Error generating emergency supply list for {user.username}: {str(e)}")

@shared_task
def send_system_update_email(subject, message, user_ids=None):
    """
    Send system updates or apology emails to users.
    Args:
        subject: Email subject
        message: HTML message content
        user_ids: Optional list of specific user IDs to send to. If None, sends to all active users.
    """
    from custom_auth.models import CustomUser
    
    try:
        # Get users to send to
        if user_ids:
            users = CustomUser.objects.filter(id__in=user_ids, is_active=True)
        else:
            users = CustomUser.objects.filter(is_active=True)

        # Load the system update email template
        project_dir = settings.BASE_DIR
        env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
        template = env.get_template('meals/system_update_email.html')
        
        for user in users:
            context = {
                'user_name': user.username,
                'message': message,
                'profile_url': f"{os.getenv('STREAMLIT_URL')}/profile"
            }

            email_body_html = template.render(context)

            email_data = {
                'subject': subject,
                'html_message': email_body_html,
                'to': user.email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
                'from': 'support@sautai.com'
            }

            try:
                n8n_url = os.getenv("N8N_SEND_SYSTEM_UPDATE_EMAIL_URL")
                response = requests.post(n8n_url, json=email_data)
                logger.info(f"System update email sent to n8n for: {user.email}")
            except Exception as e:
                logger.error(f"Error sending system update email to n8n for: {user.email}, error: {str(e)}")

    except Exception as e:
        logger.error(f"Error in send_system_update_email: {str(e)}")
        raise

@shared_task
def send_meal_plan_reminder_email():
    """
    Send reminders for unapproved meal plans on Monday for the current week's meal plan
    (which was sent on Saturday night).
    """
    from meals.models import MealPlan
    from customer_dashboard.models import GoalTracking
    
    # Get current time once
    current_utc_time = timezone.now()
    today = current_utc_time.date()
    
    # Get the date range for this week's meal plan
    this_week_start = today - timedelta(days=today.weekday())  # Monday
    this_week_end = this_week_start + timedelta(days=6)  # Sunday
    
    # Get meal plans that were created on Saturday (2 days ago) and are still unapproved
    two_days_ago = today - timedelta(days=2)
    pending_meal_plans = MealPlan.objects.filter(
        is_approved=False,
        created_date__date=two_days_ago,
        week_start_date=this_week_start,
        week_end_date=this_week_end,
        reminder_sent=False
    )

    for meal_plan in pending_meal_plans:
        user = meal_plan.user
        
        # Skip if not user's Monday
        try:
            user_timezone = pytz.timezone(user.timezone)
            user_time = current_utc_time.astimezone(user_timezone)
        except pytz.UnknownTimeZoneError:
            logger.error(f"Unknown timezone for user {user.email}: {user.timezone}")
            continue

        # Check if it's a Monday in the user's time zone
        if user_time.weekday() != 0:
            continue
         
        # Skip if user has opted out
        if not user.email_meal_plan_saved:
            continue

        try:
            # Get user's goals for motivation
            goals = GoalTracking.objects.get(user=user)
            goal_description = goals.goal_description
            
            # Create approval links with meal prep preferences
            approval_token = meal_plan.approval_token
            base_approval_url = f"{os.getenv('STREAMLIT_URL')}/meal_plans"
            
            query_params_daily = urlencode({
                'approval_token': approval_token,
                'meal_prep_preference': 'daily'
            })
            query_params_bulk = urlencode({
                'approval_token': approval_token,
                'meal_prep_preference': 'one_day_prep'
            })

            # Get meal plan details
            meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
            meals_by_day = defaultdict(list)
            for mpm in meal_plan_meals:
                meals_by_day[mpm.day].append({
                    'name': mpm.meal.name,
                    'type': mpm.meal_type
                })

            context = {
                'user_name': user.username,
                'meal_plan_week_start': this_week_start,
                'meal_plan_week_end': this_week_end,
                'approval_link_daily': f"{base_approval_url}?{query_params_daily}",
                'approval_link_bulk': f"{base_approval_url}?{query_params_bulk}",
                'profile_url': f"{os.getenv('STREAMLIT_URL')}/profile",
                'goals': goal_description,
                'meals_by_day': dict(meals_by_day)
            }

            project_dir = settings.BASE_DIR
            env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates'))) 
            template = env.get_template('meals/meal_plan_reminder_email.html')
            email_body_html = template.render(context)

            email_data = {
                'subject': "Start Your Week Right - Your Meal Plan is Waiting!",
                'html_message': email_body_html,
                'to': user.email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
                'from': 'support@sautai.com'
            }

            n8n_url = os.getenv("N8N_SEND_REMINDER_EMAIL_URL")
            response = requests.post(n8n_url, json=email_data)
            
            # Mark reminder as sent
            meal_plan.reminder_sent = True
            meal_plan.save()
            
            logger.info(f"Monday reminder email sent to n8n for: {user.email}")

        except Exception as e:
            logger.error(f"Error sending reminder email for user {user.email}: {e}")

# TODO: Set up configuration in n8n
@shared_task
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
    try:
        # Set up Jinja2 environment
        project_dir = settings.BASE_DIR
        env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
        template = env.get_template('meals/payment_confirmation_email.html')

        # Format monetary values
        amount = payment_data['amount'] / 100  # Convert cents to dollars
        service_fee = payment_data['service_fee'] / 100
        platform_fee = payment_data['platform_fee'] / 100
        net_amount = payment_data['net_amount'] / 100

        # Render the email template
        email_body_html = template.render(
            chef_name=payment_data['chef_name'],
            amount=amount,
            currency=payment_data['currency'].upper(),
            order_id=payment_data['order_id'],
            customer_name=payment_data['customer_name'],
            service_fee=service_fee,
            platform_fee=platform_fee,
            net_amount=net_amount,
            payment_date=payment_data['payment_date']
        )

        email_data = {
            'subject': f'Payment Confirmation - Order #{payment_data["order_id"]}',
            'html_message': email_body_html,
            'to': payment_data['chef_email'] if not settings.DEBUG else os.getenv('TEST_EMAIL'),
            'from': 'payments@sautai.com',
        }

        try:
            logger.debug(f"Sending payment confirmation email to n8n for: {payment_data['chef_email']}")
            n8n_url = os.getenv("N8N_PAYMENT_CONFIRMATION_EMAIL_URL")
            response = requests.post(n8n_url, json=email_data)
            response.raise_for_status()
            logger.info(f"Payment confirmation email sent to n8n for: {payment_data['chef_email']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending payment confirmation email to n8n for: {payment_data['chef_email']}, error: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error generating or sending payment confirmation email: {e}")
        logger.error(traceback.format_exc())
        raise

@shared_task
def send_refund_notification_email(order_id):
    """
    Send a refund notification email to a customer when their order is refunded.
    
    Args:
        order_id (int): ID of the ChefMealOrder that has been refunded
    """
    from meals.models import ChefMealOrder
    
    try:
        # Get the order
        order = get_object_or_404(ChefMealOrder, id=order_id)
        user = order.customer
        event = order.meal_event
        
        # Set up Jinja2 environment
        project_dir = settings.BASE_DIR
        env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
        template = env.get_template('meals/refund_notification_email.html')
        
        # Format the amount for display
        refund_amount = float(order.price_paid)
        
        # Get formatted date for the refund
        refund_date = timezone.now().strftime("%B %d, %Y")
        
        # Render the email template
        email_body_html = template.render(
            user_name=user.get_full_name() or user.username,
            order_id=order.id,
            meal_name=event.meal.name,
            chef_name=event.chef.user.get_full_name(),
            refund_amount=refund_amount,
            refund_date=refund_date,
            cancellation_reason=order.cancellation_reason,
            event_date=event.date.strftime("%B %d, %Y"),
            event_time=event.time.strftime("%I:%M %p")
        )
        
        email_data = {
            'subject': f'Your Refund for Order #{order.id} Has Been Processed',
            'html_message': email_body_html,
            'to': user.email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
            'from': 'payments@sautai.com',
        }
        
        try:
            logger.debug(f"Sending refund notification email to n8n for: {user.email}")
            n8n_url = os.getenv("N8N_REFUND_NOTIFICATION_EMAIL_URL")
            response = requests.post(n8n_url, json=email_data)
            response.raise_for_status()
            logger.info(f"Refund notification email sent to n8n for: {user.email}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending refund notification email to n8n for: {user.email}, error: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error generating or sending refund notification email for order {order_id}: {e}")

@shared_task
def send_order_cancellation_email(order_id):
    """
    Send an order cancellation notification email to a customer.
    
    Args:
        order_id (int): ID of the ChefMealOrder that has been cancelled
    """
    from meals.models import ChefMealOrder
    
    try:
        # Get the order
        order = get_object_or_404(ChefMealOrder, id=order_id)
        user = order.customer
        event = order.meal_event
        
        # Set up Jinja2 environment
        project_dir = settings.BASE_DIR
        env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
        template = env.get_template('meals/order_cancellation_email.html')
        
        # Format the amount for display if refunded
        order_amount = float(order.price_paid)
        
        # Get formatted dates
        cancellation_date = timezone.now().strftime("%B %d, %Y")
        
        # Determine if this was canceled by the chef or the customer
        canceled_by_chef = 'Event canceled by chef' in order.cancellation_reason if order.cancellation_reason else False
        
        # Render the email template
        email_body_html = template.render(
            user_name=user.get_full_name() or user.username,
            order_id=order.id,
            meal_name=event.meal.name,
            chef_name=event.chef.user.get_full_name(),
            order_amount=order_amount,
            cancellation_date=cancellation_date,
            cancellation_reason=order.cancellation_reason,
            event_date=event.date.strftime("%B %d, %Y"),
            event_time=event.time.strftime("%I:%M %p"),
            refund_status=order.refund_status if hasattr(order, 'refund_status') else None,
            canceled_by_chef=canceled_by_chef
        )
        
        email_data = {
            'subject': f'Your Order #{order.id} Has Been Cancelled',
            'html_message': email_body_html,
            'to': user.email if not settings.DEBUG else os.getenv('TEST_EMAIL'),
            'from': 'orders@sautai.com',
        }
        
        try:
            logger.debug(f"Sending order cancellation email to n8n for: {user.email}")
            n8n_url = os.getenv("N8N_CANCELLATION_EMAIL_URL")
            response = requests.post(n8n_url, json=email_data)
            response.raise_for_status()
            logger.info(f"Order cancellation email sent to n8n for: {user.email}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending order cancellation email to n8n for: {user.email}, error: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error generating or sending order cancellation email for order {order_id}: {e}")