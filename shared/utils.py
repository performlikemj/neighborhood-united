import json
import re
import traceback
import uuid
from django.shortcuts import render, redirect
from django.urls import reverse
from meals.models import PantryItem, Dish, MealType, Meal, MealPlan, MealPlanMeal, Order, OrderMeal, Ingredient, DietaryPreference, CustomDietaryPreference
from django.db import transaction, IntegrityError
from meals.pydantic_models import MealOutputSchema, RelevantSchema
from local_chefs.models import ChefPostalCode, PostalCode
from django.conf import settings
from django.conf.locale import LANG_INFO
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta, datetime
from django.db.models import Q, F
from pgvector.django import CosineDistance
from reviews.models import Review
from custom_auth.models import CustomUser, UserRole
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from .google_places import nearby_supermarkets
import os
import openai
from openai import OpenAI
from openai import OpenAIError
try:
    from groq import Groq
except ImportError:
    Groq = None
from django.utils import timezone
from django.utils.formats import date_format
from django.forms.models import model_to_dict
# Health tracking models removed - GoalTracking, UserHealthMetrics, CalorieIntake
from django.core.exceptions import ObjectDoesNotExist
import base64
import os
import requests
import logging
import numpy as np 
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
import time
from decimal import Decimal # Add this import
from typing import List, TypeVar, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# Control character regex for JSON sanitization
CTRL_CHARS = re.compile(r'[\x00-\x1F]')

T = TypeVar('T', bound=BaseModel)

def safe_parse_groq_response(
    raw: str, 
    model_cls: Type[T],
    fallback_on_error: bool = False
) -> T:
    """
    Safely parse Groq structured output response.
    
    This utility handles common JSON parsing issues from LLM responses including:
    - Control characters in the response
    - Malformed JSON syntax
    - Schema validation errors
    
    Args:
        raw: Raw JSON string from Groq API
        model_cls: Pydantic model class to validate against
        fallback_on_error: If True, return default instance on parse error
        
    Returns:
        Validated Pydantic model instance
        
    Raises:
        ValidationError: If JSON is valid but doesn't match schema
        JSONDecodeError: If JSON is malformed and fallback_on_error=False
    """
    try:
        # Try direct parsing first
        return model_cls.model_validate_json(raw)
    except json.JSONDecodeError as e:
        # Log the raw response for debugging
        logger.error(f"JSON decode error in {model_cls.__name__}: {e}. Raw response (first 1000 chars): {raw[:1000]}")
        
        # Try sanitizing control characters
        cleaned = CTRL_CHARS.sub(lambda m: '\\u%04x' % ord(m.group()), raw)
        try:
            return model_cls.model_validate_json(cleaned)
        except (json.JSONDecodeError, ValidationError) as inner_e:
            logger.error(f"Failed to parse even after sanitization: {inner_e}")
            if fallback_on_error:
                logger.warning(f"Using fallback for {model_cls.__name__}")
                return model_cls.model_construct()
            raise
    except ValidationError as e:
        logger.error(f"Validation error for {model_cls.__name__}: {e}")
        if fallback_on_error:
            logger.warning(f"Using fallback for {model_cls.__name__}")
            return model_cls.model_construct()
        raise

def get_openai_client():
    """Get OpenAI client with lazy initialization. Used only for embeddings."""
    api_key = os.getenv('OPENAI_KEY')
    if not api_key:
        raise ValueError("OPENAI_KEY not found in settings")
    return OpenAI(api_key=api_key)

def get_groq_client():
    """Get Groq client with lazy initialization for AI text generation."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in settings")
    if Groq is None:
        raise ImportError("groq package is not installed")
    return Groq(api_key=api_key)

# Helper function to get language name
def _get_language_name(language_code):
    """
    Returns the full language name for a given language code.
    Falls back to the code itself if the language is not found.
    """
    if language_code in LANG_INFO and 'name' in LANG_INFO[language_code]:
        return LANG_INFO[language_code]['name']
    return language_code

def day_to_offset(day_name: str) -> int:
    """Convert 'Monday' -> 0, 'Tuesday' -> 1, etc."""
    mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    return mapping.get(day_name, 0)

def get_dietary_preference_info(preference_name):
    """Retrieve the definition and details for a given dietary preference."""
    try:
        # Prefer custom dietary preferences (they carry detailed fields)
        custom_pref = CustomDietaryPreference.objects.filter(name=preference_name).first()
        if custom_pref:
            return {
                'exists': True,
                'description': custom_pref.description,
                'allowed': custom_pref.allowed,
                'excluded': custom_pref.excluded
            }
        
        # Fallback: predefined dietary preference exists but has no extended fields
        if DietaryPreference.objects.filter(name=preference_name).exists():
            return {
                'exists': True,
                'description': '',
                'allowed': [],
                'excluded': []
            }
        return None
    except Exception as e:
        logger.error(f"Error retrieving dietary preference info: {e}")
        return None

def create_or_update_dietary_preference(preference_name, definition, allowed, excluded):
    """
    Creates or updates a dietary preference in the database.
    This function replaces the old JSON file approach.
    """
    try:
        # Create or update the CustomDietaryPreference in the database
        custom_pref, created = CustomDietaryPreference.objects.update_or_create(
            name=preference_name,
            defaults={
                'description': definition,
                'allowed': allowed,
                'excluded': excluded
            }
        )
        
        if created:
            logger.info(f"Dietary preference '{preference_name}' created in database.")
        else:
            logger.info(f"Dietary preference '{preference_name}' updated in database.")
            
        return custom_pref
    except Exception as e:
        logger.error(f"Error saving dietary preference '{preference_name}' to database: {e}")
        logger.error(traceback.format_exc())
        return None

def append_custom_dietary_preference(request, preference_name):
    """
    Appends a new custom dietary preference to the user's preferences and triggers the Celery task for handling.
    
    Parameters:
    - request: The request object, which contains the user information.
    - preference_name: The name of the custom dietary preference as a string.

    Returns:
    - A message indicating success or failure.
    """
    try:
        print("From append_custom_dietary_preference")
        from meals.dietary_preferences import handle_custom_dietary_preference
        # Retrieve the user from the request
        user = CustomUser.objects.get(id=request.data.get('user_id'))

        # Check if the preference already exists in the user's custom preferences
        if user.custom_dietary_preferences.filter(name=preference_name).exists():
            return {"status": "info", "message": f"Preference '{preference_name}' already exists in the user's preferences."}

        # Handle the custom dietary preference
        handle_custom_dietary_preference([preference_name])

        # Add the custom preference to the user's preferences
        user.custom_dietary_preferences.create(name=preference_name)
        user.save()

        return {"status": "success", "message": f"Custom preference '{preference_name}' added to the user's preferences and task has been triggered."}

    except CustomUser.DoesNotExist:
        return {"status": "error", "message": "User not found."}

    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    logger.info(f"Generating embedding with model: {model}, text length: {len(text)}")
    try:
        # Fetch the response from the embedding API
        response = get_openai_client().embeddings.create(input=[text], model=model)
        
        # Enable detailed logging when troubleshooting
        logger.info(f"Embedding API response received, type: {type(response)}")
        
        # Access the embedding data safely
        if hasattr(response, 'data') and len(response.data) > 0:
            embedding_data = response.data[0]
            logger.info(f"Successfully extracted embedding_data from response")
            
            
            if hasattr(embedding_data, 'embedding'):
                embedding = embedding_data.embedding
                logger.info(f"Successfully extracted embedding from embedding_data")
                
                # Convert numpy arrays to lists if necessary
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                    logger.info("Converted numpy array to list")
                
                # Validate the embedding
                if is_valid_embedding(embedding):
                    logger.info(f"Valid embedding generated with length: {len(embedding)}")
                    return embedding
                else:
                    logger.error(f"Invalid embedding format or length: {len(embedding) if embedding else 'None'}")
                    return None
            else:
                logger.error("No 'embedding' attribute found in response.data[0]")
                return None
        else:
            logger.error(f"No data in embedding response: {response}")
            return None
            
    except OpenAIError as e:
        logger.error(f"OpenAI Error generating embedding: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating embedding: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        return None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Kroger API
def get_base64_encoded_credentials(client_id, client_secret):
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()

def get_access_token(client_id, client_secret):
    url = "https://api-ce.kroger.com/v1/connect/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {get_base64_encoded_credentials(client_id, client_secret)}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "product.compact"  # Adjust the scope as needed
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        # Handle error
        return None

def _get_user_id_for_ratelimit(group, request):
    """Helper function to extract user_id for rate limiting."""
    user_id = request.data.get('user_id')
    # Return user_id as string, or None if not found (though it should always be present)
    return str(user_id) if user_id else None

@ratelimit(key=_get_user_id_for_ratelimit, rate='5/d', block=True)
def find_nearby_supermarkets(request):
    """
    Find nearby supermarkets based on user's address.
    """
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    address = user.address
    latitude = address.latitude
    longitude = address.longitude
    if not latitude or not longitude:
        try:
            from shared.pydantic_models import GeoCoordinates
            user_address_string = f"The user's postal code is {address.normalized_postalcode} in the country of {address.country}"
            response = get_groq_client().chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """
                            Provide the approximate latitude and longitude coordinates for a given user's address.

                            # Steps

                            1. Analyze the given address to ensure it is properly formatted and complete.
                            2. Use your knowledge to provide approximate latitude and longitude coordinates.
                            3. Provide reasonable estimates based on the postal code and country.

                            # Output Format

                            The output should be in JSON format, structured as follows:
                            ```json
                            {
                            "latitude": [latitude_value],
                            "longitude": [longitude_value]
                            }
                            ```
                            Ensure the values are numeric and formatted with a precision of at least four decimal places. 

                            # Notes

                            - If the address is incomplete or cannot be geolocated, provide the best estimate for the region.
                            - Ensure privacy and data protection when handling user addresses.
                        """
                    },
                    {
                        "role": "user",
                        "content": user_address_string
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "GeoCoordinates",
                        "schema": GeoCoordinates.model_json_schema()
                    }
                }
            )
            geo_string = response.choices[0].message.content  # Get the JSON string
            
            # Parse the JSON string into a Python dictionary
            geo_data = json.loads(geo_string) 

            # Access latitude and longitude from the dictionary
            latitude_raw = geo_data.get("latitude") 
            longitude_raw = geo_data.get("longitude")
            
            # Format to 6 decimal places if values exist
            latitude = round(float(latitude_raw), 6) if latitude_raw is not None else None
            longitude = round(float(longitude_raw), 6) if longitude_raw is not None else None
            
            # Convert to Decimal before assigning
            user.address.latitude = Decimal(str(latitude)) if latitude is not None else None
            user.address.longitude = Decimal(str(longitude)) if longitude is not None else None

            user.address.save()
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding Geo JSON: {e}")
            logger.error(f"Received geo string: {geo_string}")
            return {"status": "error", "message": "Failed to parse location data."}
        except Exception as e:
            logger.error(f"Error getting latitude and longitude: {e}")
            return {"status": "error", "message": str(e)}

    try:
        supermarkets = nearby_supermarkets(latitude, longitude)
        return {"status": "success", "data": supermarkets}
    except Exception as e:
        logger.error(f"Google Places error: {e}")
        return {"status": "error", "message": str(e)}

# sautai functions

def generate_user_context(user):
    """Creates a detailed user context prompt with location, timezone, language, and household member information."""
    
    # Convert predefined dietary preferences QuerySet to a comma-separated string
    predefined_dietary_preferences = ', '.join([pref.name for pref in user.dietary_preferences.all()]) if user.dietary_preferences.exists() else "None"
    
    # Handle multiple custom dietary preferences (ManyToManyField)
    custom_preferences = user.custom_dietary_preferences.all()
    
    custom_preferences_info = []
    allowed_foods_list = []
    excluded_foods_list = []
    
    if custom_preferences.exists():
        for custom_pref in custom_preferences:
            dietary_pref_info = get_dietary_preference_info(custom_pref.name)
            if dietary_pref_info:
                description = dietary_pref_info.get('description') or ''
                allowed = dietary_pref_info.get('allowed') or []
                excluded = dietary_pref_info.get('excluded') or []
                custom_preferences_info.append(f"{custom_pref.name}: {description}")
                allowed_foods_list.extend(allowed)
                excluded_foods_list.extend(excluded)
            else:
                custom_preferences_info.append(f"Custom preference '{custom_pref.name}' is being researched and will be added soon.")
    else:
        custom_preferences_info.append("None")
    
    # Combine dietary preferences into a string
    custom_dietary_preference_str = ', '.join(custom_preferences_info)
    
    # Combine allowed and excluded foods
    allowed_foods_str = ', '.join(allowed_foods_list) if allowed_foods_list else "None"
    excluded_foods_str = ', '.join(excluded_foods_list) if excluded_foods_list else "None"
    
    combined_allergies = set((user.allergies or []) + (user.custom_allergies or []))
    allergies_str = ', '.join(combined_allergies) if combined_allergies else 'None'
    
    # Get user goals
    goals = user.goal.goal_description if hasattr(user, 'goal') and user.goal else "None"

    # Get user location details from the Address model
    if hasattr(user, 'address') and user.address:
        address = user.address
        city = address.city if address.city else "Unknown City"
        state = address.state if address.state else "Unknown State"
        country = address.country.name if address.country else "Unknown Country"
    else:
        city = "Unknown City"
        state = "Unknown State"
        country = "Unknown Country"
    
    # Get user's timezone
    timezone = user.timezone if user.timezone else "UTC"
    
    # Get user's preferred language
    # Try to get language name from Django's LANG_INFO instead of relying on LANGUAGE_CHOICES
    from django.conf.locale import LANG_INFO
    lang_code = user.preferred_language if user.preferred_language else "en"
    try:
        # Try to get the language info, first check direct match
        if lang_code in LANG_INFO:
            preferred_language = LANG_INFO[lang_code]['name']
        else:
            # If we have a composite code like 'en-us', try the base code 'en'
            base_lang_code = lang_code.split('-')[0]
            preferred_language = LANG_INFO.get(base_lang_code, {}).get('name', "English")
    except (KeyError, AttributeError):
        # Fallback to English if language code isn't found
        preferred_language = "English"
    
    # NEW: Get detailed household member information
    household_info = ""
    if hasattr(user, 'household_members'):
        household_members = user.household_members.all()
        if household_members.exists():
            household_info = f"- Household Members ({len(household_members)} total):\n"
            for member in household_members:
                member_dietary_prefs = ', '.join([pref.name for pref in member.dietary_preferences.all()]) if member.dietary_preferences.exists() else "None"
                age_info = f", Age: {member.age}" if member.age else ""
                notes_info = f", Notes: {member.notes}" if member.notes else ""
                household_info += f"  • {member.name}{age_info}, Dietary Preferences: {member_dietary_prefs}{notes_info}\n"
        else:
            household_info = f"- Household Size: {getattr(user, 'household_member_count', 1)} members (no individual details provided)\n"
    else:
        household_info = f"- Household Size: {getattr(user, 'household_member_count', 1)} members (no individual details provided)\n"
    
    # Combine all information into a structured context
    user_preferences = (
        f"User Preferences:\n"
        f"- Predefined Dietary Preferences: {predefined_dietary_preferences}\n"
        f"- Custom Dietary Preferences: {custom_dietary_preference_str}\n"
        f"- Allowed Foods: {allowed_foods_str}\n"
        f"- Excluded Foods: {excluded_foods_str}\n"
        f"- Allergies: {allergies_str}\n"
        f"- Goals: {goals}\n"
        f"{household_info}"
        f"- Location: {city}, {state}, {country}\n"
        f"- Timezone: {timezone}\n"
        f"- Preferred Language: {preferred_language}"
    )
    
    age_note = build_age_safety_note(user)
    if age_note:
        user_preferences += f"\n{age_note}"

    return user_preferences


def generate_family_context_for_chef(chef, customer=None, lead=None):
    """
    Generate comprehensive family context for the Sous Chef assistant.
    
    This function creates a detailed context string about a family (either a 
    platform customer or CRM lead) that helps the chef's AI assistant provide
    personalized meal planning and preparation advice.
    
    Args:
        chef: The Chef instance who is using the Sous Chef
        customer: Optional CustomUser instance (platform customer)
        lead: Optional Lead instance (off-platform contact from CRM)
        
    Returns:
        str: A formatted context string with family information
    """
    from chef_services.models import ChefCustomerConnection, ChefServiceOrder
    from meals.models import ChefMealEvent, ChefMealOrder
    from crm.models import Lead, LeadInteraction, LeadHouseholdMember
    from chefs.services import get_client_stats
    from decimal import Decimal
    
    if not customer and not lead:
        return "No family context available."
    
    context_parts = []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PLATFORM CUSTOMER CONTEXT
    # ═══════════════════════════════════════════════════════════════════════════
    if customer:
        # Basic family info
        family_name = f"{customer.first_name} {customer.last_name}".strip() or customer.username
        context_parts.append(f"## Family: {family_name}")
        context_parts.append(f"- **Contact Email**: {customer.email}")
        
        # Household size
        household_size = getattr(customer, 'household_member_count', 1)
        context_parts.append(f"- **Household Size**: {household_size} members")
        
        # Primary contact dietary preferences
        dietary_prefs = ', '.join([pref.name for pref in customer.dietary_preferences.all()]) if customer.dietary_preferences.exists() else "None specified"
        context_parts.append(f"- **Primary Contact Dietary Preferences**: {dietary_prefs}")
        
        # Custom dietary preferences
        custom_prefs = customer.custom_dietary_preferences.all()
        if custom_prefs.exists():
            custom_names = ', '.join([p.name for p in custom_prefs])
            context_parts.append(f"- **Custom Dietary Preferences**: {custom_names}")
        
        # Allergies
        combined_allergies = set((customer.allergies or []) + (customer.custom_allergies or []))
        allergies_str = ', '.join(combined_allergies) if combined_allergies else "None reported"
        context_parts.append(f"- **Allergies**: {allergies_str}")
        
        # Household members
        if hasattr(customer, 'household_members'):
            household_members = customer.household_members.all()
            if household_members.exists():
                context_parts.append("\n### Household Members")
                for member in household_members:
                    member_line = f"- **{member.name}**"
                    if member.age:
                        member_line += f" (Age: {member.age})"
                    
                    member_dietary = ', '.join([pref.name for pref in member.dietary_preferences.all()]) if member.dietary_preferences.exists() else None
                    if member_dietary:
                        member_line += f" — Dietary: {member_dietary}"
                    
                    if member.notes:
                        member_line += f" — Notes: {member.notes}"
                    
                    context_parts.append(member_line)
        
        # Connection status with this chef
        try:
            connection = ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer
            ).first()
            if connection:
                context_parts.append(f"\n### Connection Status")
                context_parts.append(f"- **Status**: {connection.get_status_display()}")
                if connection.responded_at:
                    context_parts.append(f"- **Connected Since**: {connection.responded_at.strftime('%B %d, %Y')}")
                if connection.notes:
                    context_parts.append(f"- **Connection Notes**: {connection.notes}")
        except Exception:
            pass
        
        # Order history and stats
        try:
            stats = get_client_stats(chef, customer)
            context_parts.append(f"\n### Order History with You")
            context_parts.append(f"- **Total Orders**: {stats.get('total_orders', 0)}")
            total_spent = stats.get('total_spent', Decimal('0'))
            context_parts.append(f"- **Total Spent**: ${total_spent:.2f}")
            
            if stats.get('last_order_date'):
                context_parts.append(f"- **Last Order**: {stats['last_order_date'].strftime('%B %d, %Y')}")
            
            favorite_services = stats.get('favorite_services', [])
            if favorite_services:
                fav_names = ', '.join([f"{s['name']} ({s['order_count']} orders)" for s in favorite_services[:3]])
                context_parts.append(f"- **Favorite Services**: {fav_names}")
        except Exception:
            pass
        
        # Recent interaction notes (from CRM Lead if linked)
        try:
            linked_lead = Lead.objects.filter(owner=chef.user, email=customer.email).first()
            if linked_lead:
                recent_notes = LeadInteraction.objects.filter(
                    lead=linked_lead,
                    is_deleted=False
                ).order_by('-happened_at')[:5]
                
                if recent_notes.exists():
                    context_parts.append(f"\n### Recent Notes")
                    for note in recent_notes:
                        note_date = note.happened_at.strftime('%m/%d/%Y')
                        context_parts.append(f"- **{note.get_interaction_type_display()}** ({note_date}): {note.summary}")
                        if note.next_steps:
                            context_parts.append(f"  - Next steps: {note.next_steps}")
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRM LEAD CONTEXT (Off-platform contact)
    # ═══════════════════════════════════════════════════════════════════════════
    elif lead:
        family_name = f"{lead.first_name} {lead.last_name}".strip()
        context_parts.append(f"## Family: {family_name}")
        context_parts.append(f"- **Type**: Off-platform contact (CRM Lead)")
        
        if lead.email:
            context_parts.append(f"- **Contact Email**: {lead.email}")
        if lead.phone:
            context_parts.append(f"- **Phone**: {lead.phone}")
        
        # Lead status and source
        context_parts.append(f"- **Status**: {lead.get_status_display()}")
        context_parts.append(f"- **Source**: {lead.get_source_display()}")
        
        # Household size
        context_parts.append(f"- **Household Size**: {lead.household_size} members")
        
        # Dietary preferences
        if lead.dietary_preferences:
            prefs = ', '.join(lead.dietary_preferences)
            context_parts.append(f"- **Dietary Preferences**: {prefs}")
        else:
            context_parts.append(f"- **Dietary Preferences**: None specified")
        
        # Allergies
        all_allergies = list(lead.allergies or []) + list(lead.custom_allergies or [])
        allergies_str = ', '.join(all_allergies) if all_allergies else "None reported"
        context_parts.append(f"- **Allergies**: {allergies_str}")
        
        # Lead notes
        if lead.notes:
            context_parts.append(f"- **Notes**: {lead.notes}")
        
        # Household members
        household_members = lead.household_members.all()
        if household_members.exists():
            context_parts.append(f"\n### Household Members")
            for member in household_members:
                member_line = f"- **{member.name}**"
                if member.relationship:
                    member_line += f" ({member.relationship})"
                if member.age:
                    member_line += f" — Age: {member.age}"
                
                if member.dietary_preferences:
                    member_prefs = ', '.join(member.dietary_preferences)
                    member_line += f" — Dietary: {member_prefs}"
                
                member_allergies = list(member.allergies or []) + list(member.custom_allergies or [])
                if member_allergies:
                    member_line += f" — Allergies: {', '.join(member_allergies)}"
                
                if member.notes:
                    member_line += f" — Notes: {member.notes}"
                
                context_parts.append(member_line)
        
        # Interaction history
        interactions = LeadInteraction.objects.filter(
            lead=lead,
            is_deleted=False
        ).order_by('-happened_at')[:5]
        
        if interactions.exists():
            context_parts.append(f"\n### Recent Interactions")
            for interaction in interactions:
                int_date = interaction.happened_at.strftime('%m/%d/%Y')
                context_parts.append(f"- **{interaction.get_interaction_type_display()}** ({int_date}): {interaction.summary}")
                if interaction.next_steps:
                    context_parts.append(f"  - Next steps: {interaction.next_steps}")
        
        # Budget info
        if lead.budget_cents:
            budget = Decimal(lead.budget_cents) / 100
            context_parts.append(f"\n- **Budget**: ${budget:.2f}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMBINED DIETARY SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    context_parts.append("\n### Dietary Compliance Summary")
    
    # Aggregate all dietary restrictions and allergies across household
    all_restrictions = set()
    all_allergies = set()
    
    if customer:
        all_restrictions.update(pref.name for pref in customer.dietary_preferences.all())
        all_allergies.update(customer.allergies or [])
        all_allergies.update(customer.custom_allergies or [])
        
        if hasattr(customer, 'household_members'):
            for member in customer.household_members.all():
                all_restrictions.update(pref.name for pref in member.dietary_preferences.all())
    
    elif lead:
        all_restrictions.update(lead.dietary_preferences or [])
        all_allergies.update(lead.allergies or [])
        all_allergies.update(lead.custom_allergies or [])
        
        for member in lead.household_members.all():
            all_restrictions.update(member.dietary_preferences or [])
            all_allergies.update(member.allergies or [])
            all_allergies.update(member.custom_allergies or [])
    
    if all_restrictions:
        context_parts.append(f"- **All Dietary Restrictions**: {', '.join(sorted(all_restrictions))}")
    else:
        context_parts.append("- **All Dietary Restrictions**: None")
    
    if all_allergies:
        context_parts.append(f"- **⚠️ All Allergies (MUST AVOID)**: {', '.join(sorted(all_allergies))}")
    else:
        context_parts.append("- **All Allergies**: None reported")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SAVED INSIGHTS (Persistent learnings about this family)
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        from customer_dashboard.models import FamilyInsight
        
        insight_filter = {'chef': chef, 'is_active': True}
        if customer:
            insight_filter['customer'] = customer
            insight_filter['lead__isnull'] = True
        elif lead:
            insight_filter['lead'] = lead
            insight_filter['customer__isnull'] = True
        
        insights = FamilyInsight.objects.filter(**insight_filter).order_by('-created_at')[:10]
        
        if insights.exists():
            context_parts.append("\n### Saved Insights About This Family")
            context_parts.append("*(Persistent learnings from previous conversations)*")
            
            # Group by type
            by_type = {
                'preference': [],
                'tip': [],
                'avoid': [],
                'success': []
            }
            for insight in insights:
                by_type[insight.insight_type].append(insight.content)
            
            type_labels = {
                'preference': '🎯 Preferences',
                'tip': '💡 Tips',
                'avoid': '🚫 Things to Avoid',
                'success': '✅ What Worked Well'
            }
            
            for itype, label in type_labels.items():
                if by_type[itype]:
                    context_parts.append(f"\n**{label}**:")
                    for content in by_type[itype]:
                        context_parts.append(f"- {content}")
    except Exception:
        pass  # Insights are optional, don't fail context generation
    
    return '\n'.join(context_parts)


def understand_dietary_choices(request):
    dietary_choices = Meal.dietary_preferences   
    return dietary_choices

def provide_healthy_meal_suggestions(request, user_id):
    user = CustomUser.objects.get(id=user_id)

    user_info = {
        'goal_name': user.goal.goal_name,
        'goal_description': user.goal.goal_description,
        'dietary_preference': user.dietary_preferences.all()
    }

    return user_info

def search_healthy_meal_options(request, search_term, location_id, limit=10, start=0):
    url = "https://api-ce.kroger.com/v1/products"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {get_access_token(client_id=os.getenv('KROGER_CLIENT_ID'), client_secret=os.getenv('KROGER_CLIENT_SECRET'))}"
    }
    params = {
        "filter.term": search_term,
        "filter.locationId": location_id,
        "filter.limit": limit,
        "filter.start": start
    }
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle errors
        return None

def is_question_relevant(question):
    """
    Determine if a question is relevant to the application's functionality, specifically considering health, nutrition, and diet.

    :param question: A string representing the user's question.
    :return: A boolean indicating whether the question is relevant.
    """
    print("From is_question_relevant")

    # Define application's functionalities and domains for the model to consider
    app_context = """
    The application focuses on food delivery, meal planning, health, nutrition, and diet. It allows users to:
    - Communicate with their personal AI powered dietary assistant. The user should be able to greet the assistant and start a conversation with it.
    - Create meal plans with meals geared towards their goals.
    - Search for dishes and ingredients.
    - Get personalized meal plans based on dietary preferences and nutritional goals.
    - Find chefs and meal delivery options catering to specific dietary needs.
    - Track calorie intake and provide nutrition advice.
    - Access information on healthy meal options and ingredients.
    """

    response = get_groq_client().chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": """
                    Determine if a given question is relevant to the application's functionalities related to food delivery, meal planning, health, nutrition, and diet, and return 'True' for relevant or 'False' for non-relevant questions.

                    # Steps

                    1. **Understand the Application Context**: Familiarize yourself with the key functionalities of the application:
                    - Communicate with their personal AI powered dietary assistant. The user should be able to greet the assistant and start a conversation with it.
                    - Creating and personalizing meal plans.
                    - Searching for dishes and ingredients.
                    - Providing personalized meal plans based on dietary preferences and nutritional goals.
                    - Finding chefs and meal delivery options for specific dietary needs.
                    - Tracking calorie intake and offering nutrition advice.
                    - Accessing information on healthy meal options and ingredients.

                    2. **Analyze the Question**: Break down the given question to understand its core objective and the context it fits into.

                    3. **Relevance Assessment**: Compare the analyzed question against the application's functionalities:
                    - If the question touches on any of the points mentioned in the application context, consider it relevant.
                    - If the question does not relate to any of the functionalities, consider it non-relevant.

                    4. **Decision**: Based on your analysis, decide whether the question is relevant ('True') or not ('False').

                    # Output Format

                    - Return 'True' if the question is relevant to the application's functionalities.
                    - Return 'False' if the question is not relevant.

                    # Examples

                    - **Input**: "How do I find a low-carb meal plan?"
                    - **Analysis**: The question relates to creating personalized meal plans; it is relevant.
                    - **Output**: True

                    - **Input**: "Can I book a flight through the app?"
                    - **Analysis**: The question does not relate to the application's functionalities; it is not relevant.
                    - **Output**: False

                    # Notes

                    - Pay close attention to questions that may be indirectly related to the functionalities and evaluate them carefully.
                    - The user should be able to communicate with the assistant in a friendly tone which should be relevant as long as it does not go against the application's context.
                    - The user should be able to start a conversation and engage in 'small talk' with the assistant, but should not veer into dangerous topics.
                    - Ensure that the response strictly adheres to the functionalities outlined in the application's context.
                """
            },
            {
                "role": "user",
                "content": (
                    f"given the {question}, determine if the question is relevant to the application's functionalities by returning a 'True' if relevant and 'False' if not."         
                )
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "Instructions", 
                "schema": RelevantSchema.model_json_schema()
            }
        }
    )

    # Interpret the model's response
    response_content = response.choices[0].message.content
    relevant = json.loads(response_content).get('relevant', False)
    return relevant

def recommend_follow_up(request, context):
    """
    Recommend follow-up prompts based on the user's interaction context.

    :param context: A string representing the user's last few interactions or context.
    :return: A list of recommended follow-up prompts or actions.
    """
    from shared.pydantic_models import FollowUpList as FollowUpSchema
    if request.data.get('user_id'):
        user_id = request.data.get('user_id')
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            user = None
    else:
        user = None

    if user and user.is_authenticated:
        functions = """
            # Meal Planning Tools
            "create_meal_plan": "Create a meal plan for the user",
            "modify_meal_plan": "Modify a meal plan for the user",
            "get_meal_plan": "Get a meal plan for the user",
            "generate_meal_instructions": "Generate meal instructions for the user",
            "get_user_info": "Get user information",
            "get_current_date": "Get the current date",
            "list_upcoming_meals": "List upcoming meals for the user",
            "find_nearby_supermarkets": "Find nearby supermarkets for the user",
            "update_user_info": "Update user information",
            
            # Pantry Management Tools
            "check_pantry_items": "Check pantry items for the user",
            "add_pantry_item": "Add a pantry item for the user",
            "get_expiring_items": "Get expiring items for the user",
            "generate_shopping_list": "Generate a shopping list for the user",
            
            # Chef Connection Tools
            "find_local_chefs": "Find local chefs for the user",
            "get_chef_details": "Get chef details for the user",
            "view_chef_meal_events": "View chef meal events for the user",
            "place_chef_meal_event_order": "Place a chef meal event order for the user",
            "get_order_details": "Get order details for the user",
            "cancel_order": "Cancel an order for the user",
            
            # Payment Processing Tools
            "create_payment_link": "Create a payment link for the user",
            "check_payment_status": "Check a payment status for the user",
            "process_refund": "Process a refund for the user",
            
            # Dietary Preference Tools
            "manage_dietary_preferences": "Manage dietary preferences for the user",
            "check_meal_compatibility": "Check meal compatibility for the user",
            "suggest_alternatives": "Suggest alternatives for the user",
            "check_allergy_alert": "Check an allergy alert for the user",

            # Customer Dashboard Tools
            "adjust_week_shift": "Adjust a week shift for the user",
            "reset_current_week": "Reset a current week for the user",
            "update_goal": "Update a goal for the user",
            "get_goal": "Get a goal for the user",
            "access_past_orders": "Access past orders for the user",

            # Guest Tools
            "guest_search_dishes": "Search dishes in the database",
            "guest_search_chefs": "Search chefs in the database",
            "guest_get_meal_plan": "Get a meal plan for the current week",
            "guest_search_ingredients": "Search ingredients used in dishes",
            "chef_service_areas": "Get chef service areas"
        }
    """
    else:
        print("Chatting with Guest GPT")
        functions = """
            "guest_search_dishes: Search dishes in the database",
            "guest_search_chefs: Search chefs in the database and get their info",
            "guest_get_meal_plan: Get a meal plan for the current week",
            "guest_search_ingredients: Search ingredients used in dishes and get their info",
            "get_current_date: Get the current date"    
        """

    try:
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze the full context of the message so far. "
                        "Given the library of tools available, suggest recommended follow-up questions to ask the meal planning assistant. "
                        "Ensure that recommendations align strictly with the scope of the available tools, and do not invent anything outside of it."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Given the following context: {context} and functions: {functions}, "
                        f"Answering in the user's language of {user.preferred_language}, "
                        f"what prompt should a user write next? Output ONLY the recommended prompt in the first person and in a natural sentence "
                        f"without using the function name, without quotations, and without starting the output with 'the user should write' or anything similar."
                    )
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "follow_up",
                    "schema": FollowUpSchema.model_json_schema()
                }
            }
        )
        # Get the response content from Groq
        response_content = response.choices[0].message.content
        return response_content.strip().split('\n')

    except Exception as e:
        return f"An error occurred: {str(e)}"


def provide_nutrition_advice(request, user_id):
    """Legacy function - health tracking removed. Returns user dietary info only."""
    try:
        user = CustomUser.objects.get(id=user_id)
        user_role = UserRole.objects.get(user=user)

        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        # Health tracking removed - return dietary preferences only
        return {
            'status': 'success',
            'goal_info': {'goal_name': 'None', 'goal_description': 'Goal tracking removed'},
            'health_metrics': {'weight': 'N/A', 'bmi': 'N/A', 'mood': 'N/A', 'energy_level': 'N/A'},
            'dietary_preferences': list(user.dietary_preferences.values_list('name', flat=True)),
            'allergies': user.allergies or [],
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        return {'status': 'error', 'message': f'An unexpected error occurred: {e}', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

#TODO: Create function to add allergies if user mentions it

def check_allergy_alert(request, user_id):
    print("From check_allergy_alert")
    user = CustomUser.objects.get(id=user_id)
    user_role = UserRole.objects.get(user=user)
    
    # Check if the user's current role is 'chef' and restrict access
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    # Directly return the list of allergies. Since 'user.allergies' is an ArrayField, it's already a list.
    return {'Allergens': user.allergies}

def update_health_metrics(request, user_id, weight=None, bmi=None, mood=None, energy_level=None):
    """Legacy function - health tracking has been removed."""
    return "Health tracking has been removed from this application."

def get_unupdated_health_metrics(request, user_id):
    """Legacy function - health tracking has been removed."""
    return "Health tracking has been removed from this application."


def adjust_week_shift(request, week_shift_increment):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Update the user's week shift, ensuring it doesn't go below 0
    new_week_shift = user.week_shift + week_shift_increment
    if new_week_shift < 0:
        return {'status': 'error', 'message': 'Week shift cannot be negative.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    else:
        user.week_shift = new_week_shift
        user.save()

    return {
        'status': 'success',
        'message': f'Week shift adjusted to {new_week_shift} weeks.',
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def update_goal(request, goal_name, goal_description):
    """Legacy function - goal tracking has been removed."""
    return {
        'status': 'error', 
        'message': 'Goal tracking has been removed from this application.',
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def get_goal(request):
    """Legacy function - goal tracking has been removed."""
    return {
        'status': 'error',
        'message': 'Goal tracking has been removed from this application.',
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def get_user_info(request):
    """Get basic user info - health/goal tracking removed."""
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        address = Address.objects.get(user=user)
        postal_code = address.normalized_postalcode if address.normalized_postalcode else 'Not provided'
        if isinstance(postal_code, str) and postal_code.isdigit():
            postal_code = int(postal_code)

        # Normalize country to a JSON-serializable string (prefer ISO code)
        if address.country:
            try:
                country = getattr(address.country, 'code', None) or str(address.country)
            except Exception:
                country = 'Not provided'
        else:
            country = 'Not provided'
        allergies = user.allergies if user.allergies != [{}] else []

        # Convert the QuerySet to a list of values (e.g., names of dietary preferences)
        dietary_preferences = list(user.dietary_preferences.values_list('name', flat=True))

        user_info = {
            'user_id': user.id,
            'dietary_preference': dietary_preferences,
            'week_shift': user.week_shift,
            'user_goal': 'Goal tracking removed',
            'postal_code': postal_code,
            'country': country,
            'allergies': allergies,  
        }
        return {'status': 'success', 'user_info': user_info, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Address.DoesNotExist:
        return {'status': 'error', 'message': 'Address not found for user.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def update_user_info(request):
    """
    Update the user's information (goal tracking removed).
    """
    try:
        data = json.loads(request._body)
        user_id = data.get('user_id')
        user = CustomUser.objects.get(id=user_id)

        # Update address information
        address, created = Address.objects.get_or_create(user=user)
        postal_code = data.get('postal_code', None)
        if postal_code:
            address.input_postalcode = postal_code
        street = data.get('street', None)
        if street:
            address.street = street
        city = data.get('city', None)
        if city:
            address.city = city
        state = data.get('state', None)
        if state:
            address.state = state
        country = data.get('country', None)
        if country:
            address.country = country
        address.save()

        # Update dietary preferences
        dietary_preferences = data.get('dietary_preferences', None)
        if dietary_preferences is not None:
            user.dietary_preferences.clear()
            for pref in dietary_preferences:
                clean_name = pref.strip().strip('"').strip("'")
                dietary_preference, _ = DietaryPreference.objects.get_or_create(
                    name__iexact=clean_name,   # exact, case-insensitive
                    defaults={"name": clean_name}
                )
                user.dietary_preferences.add(dietary_preference)
        # Update allergies
        allergies = data.get('allergies', None)
        if allergies is not None:
            user.allergies = allergies

        # Note: Goal tracking has been removed from this application

        user.save()
        return {'status': 'success', 'message': 'User information updated successfully'}

    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        traceback.print_exc()
        return {'status': 'error', 'message': str(e)}
    
def access_past_orders(request, user_id):
    try:
        # Check user authorization
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        # Find meal plans within the week range with specific order statuses
        meal_plans = MealPlan.objects.filter(
            user_id=user_id,
            order__status__in=['Completed', 'Cancelled', 'Refunded']
        )

        # If no meal plans are found, return a message
        if not meal_plans.exists():
            return {'status': 'info', 'message': "No meal plans found for the current week.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        # Retrieve orders associated with the meal plans
        orders = Order.objects.filter(meal_plan__in=meal_plans)

        # If no orders are found, return a message indicating this
        if not orders.exists():
            return {'status': 'info', 'message': "No past orders found.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        # Prepare order data
        orders_data = []
        for order in orders:
            order_meals = order.ordermeal_set.all()
            if not order_meals:
                continue
            meals_data = [{'meal_id': om.meal.id, 'quantity': om.quantity} for om in order_meals]
            order_data = {
                'order_id': order.id,
                'order_date': order.order_date.strftime('%Y-%m-%d'),
                'status': order.status,
                'total_price': order.total_price() if order.total_price() is not None else 0,
                'meals': meals_data
            }
            orders_data.append(order_data)
        return {'orders': orders_data, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except KeyError as e:
        return {'status': 'error', 'message': f"Missing parameter: {str(e)}"}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': "User not found."}
    except UserRole.DoesNotExist:
        return {'status': 'error', 'message': "User role not found."}
    except Exception as e:
        return {'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"}    

def post_review(request, user_id, content, rating, item_id, item_type):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})
    
    # Find the content type based on item_type
    if item_type == 'chef':
        content_type = ContentType.objects.get_for_model(Chef)
        # Check if the user has purchased a meal from the chef
        if not Meal.objects.filter(chef__id=item_id, ordermeal__order__customer_id=user_id).exists():
            return {'status': 'error', 'message': 'You have not purchased a meal from this chef.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    elif item_type == 'meal':
        content_type = ContentType.objects.get_for_model(Meal)
        # Check if the order status for the reviewed item is either 'Completed', 'Cancelled', or 'Refunded'
        if not OrderMeal.objects.filter(meal_id=item_id, order__customer_id=user_id, order__status__in=['Completed', 'Cancelled', 'Refunded']).exists():
            return {'status': 'error', 'message': 'You have not completed an order for this meal.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    else:
        return {'status': 'error', 'message': 'Only meals and chefs can be reviewed.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Create and save the review
    review = Review(
        user_id=user_id, 
        content=content, 
        rating=rating, 
        content_type=content_type, 
        object_id=item_id
    )
    review.save()

    return {'status': 'success', 'message': 'Review posted successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def update_review(request, review_id, updated_content, updated_rating):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    if user.id != Review.objects.get(id=review_id).user.id:
        return {'status': 'error', 'message': 'You are not authorized to update this review.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    review = Review.objects.get(id=review_id)
    review.content = updated_content
    review.rating = updated_rating
    review.save()

    return {'status': 'success', 'message': 'Review updated successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def delete_review(request, review_id):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    if user.id != Review.objects.get(id=review_id).user.id:
        return {'status': 'error', 'message': 'You are not authorized to delete this review.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    review_id = request.POST.get('review_id')

    review = Review.objects.get(id=review_id)
    review.delete()

    return {'status': 'success', 'message': 'Review deleted successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

#TODO: turn this into a celery task coupled with a signal
def generate_review_summary(object_id, category):
    # Step 1: Fetch all the review summaries for a specific chef or meal
    content_type = ContentType.objects.get(model=category)
    model_class = content_type.model_class()
    reviews = Review.objects.filter(content_type=content_type, object_id=object_id)

    if not reviews.exists():
        return {"message": "No reviews found.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Step 2: Format the summaries naturally
    formatted_summaries = "Review summaries:\n"
    for review in reviews:
        formatted_summaries += f" - {review.content}\n"

    # Step 3: Feed the formatted string into Groq to generate the overall summary
    try:
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": formatted_summaries}],
        )
        overall_summary = response.choices[0].message.content
    except Exception as e:
        return {"message": f"An error occurred: {str(e)}", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Step 4: Store the overall summary in the database
    obj = model_class.objects.get(id=object_id)
    obj.review_summary = overall_summary
    obj.save()

    
    # Step 5: Return the overall summary
    return {"overall_summary": overall_summary, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

# Function to generate a summarized title
def generate_summary_title(question):
    try:
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates concise titles for chat conversations."
                },
                {
                    "role": "user",
                    "content": f"Summarize this question for a chat title: {question}"
                }
            ],
        )
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        return question[:254]  # Fallback to truncating the question if an error occurs



def list_upcoming_meals(request):
    user = CustomUser.objects.get(id=request.data.get("user_id"))
    user_role = UserRole.objects.get(user=user)
    if user_role.current_role == 'chef':
        return {
            'status': 'error',
            'message': 'Chefs in their chef role are not allowed to use the assistant.'
        }

    today = timezone.now().date()

    # Grab all future (or today's) slots across every MealPlan for this user
    slots = (
        MealPlanMeal.objects
        .filter(meal_plan__user=user, meal_date__gte=today)
        .select_related('meal', 'meal_plan')
        .order_by('meal_date', 'meal_type')
    )

    if not slots.exists():
        return {
            'status': 'info',
            'message': 'You have no upcoming meals scheduled.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    meal_details = [
        {
            "meal_id": slot.meal.id,
            "name": slot.meal.name,
            "date": slot.meal_date.isoformat(),
            "meal_type": slot.meal_type,
            "chef_meals_for_ordering": slot.meal.can_be_ordered(),
            "chef": slot.meal.chef.user.username if slot.meal.chef else 'User Created Meal'
        }
        for slot in slots
    ]

    return {
        "upcoming_meals": meal_details,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def create_meal_plan(request):
    print("From create_meal_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Calculate the week's date range which also works if user shifts week
    week_shift = max(int(user.week_shift), 0)  # Ensure week_shift is not negative
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)


    # Check if a MealPlan already exists for the specified week
    if not MealPlan.objects.filter(user=user, week_start_date=start_of_week, week_end_date=end_of_week).exists():
        # Create a new MealPlan for the remaining days in the week
        meal_plan = MealPlan.objects.create(
            user=user,
            week_start_date=start_of_week,
            week_end_date=end_of_week,
            created_date=timezone.now(),
            approval_token=uuid.uuid4()
        )
        return {'status': 'success', 'message': 'Created new meal plan. It is currently empty.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {'status': 'error', 'message': 'A meal plan already exists for this week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def replace_meal_in_plan(request, meal_plan_id, old_meal_id, new_meal_id, day, meal_type):
    logger.info("Initiating meal replacement process for user.")
    
    # Resolve user safely
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'id', None):
        # Attempt to read from payload as fallback
        user_id = None
        data = getattr(request, 'data', None)
        if isinstance(data, dict):
            user_id = data.get('user_id') or data.get('userId') or data.get('id')
        if user_id:
            user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            logger.error("Authenticated user not found for replace_meal_in_plan.")
            return {'status': 'error', 'message': 'Authenticated user not found. Please ensure you are logged in.'}
    
    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        logger.error(f"Meal plan with ID {meal_plan_id} not found for user {user.username}.")
        return {'status': 'error', 'message': 'Meal plan not found.'}
    
    # Validate old and new meals
    try:
        old_meal = Meal.objects.get(id=old_meal_id)
        new_meal = Meal.objects.get(id=new_meal_id)
    except Meal.DoesNotExist as e:
        logger.error(f"Meal not found: {str(e)}")
        return {'status': 'error', 'message': f'Meal not found: {str(e)}'}
    
    # Validate day and meal type
    if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
        logger.error(f"Invalid day: {day}.")
        return {'status': 'error', 'message': f'Invalid day: {day}. Accepted days are: {", ".join(dict(MealPlanMeal.DAYS_OF_WEEK).keys())}'}
    
    if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
        logger.error(f"Invalid meal type: {meal_type}.")
        return {'status': 'error', 'message': f'Invalid meal type (BREAKFAST, LUNCH, DINNER): {meal_type}. Accepted types are: {", ".join(dict(MealPlanMeal.MEAL_TYPE_CHOICES).keys())}'}
    
    # Transaction block to ensure atomicity
    try:
        with transaction.atomic():
            # Use update_or_create to atomically update or create the MealPlanMeal
            offset = day_to_offset(day)
            meal_date = meal_plan.week_start_date + timedelta(days=offset)

            meal_plan_meal, created = MealPlanMeal.objects.update_or_create(
                meal_plan=meal_plan,
                day=day,
                meal_type=meal_type,
                meal_date=meal_date,
                defaults={'meal': new_meal}
            )
            
            if created:
                logger.info(f"Created new MealPlanMeal: {meal_plan_meal}")
            else:
                logger.info(f"Updated existing MealPlanMeal: {meal_plan_meal}")
            
            meal_plan.has_changes = True
            meal_plan.is_approved = False
            meal_plan.save()
            logger.info(f"Replaced meal '{old_meal.name}' with '{new_meal.name}' for {meal_type} on {day}.")
    
    except IntegrityError as e:
        logger.error(f"IntegrityError while replacing meal: {e}")
        logger.error(traceback.format_exc())
        return {'status': 'error', 'message': 'A meal for this day and meal type already exists.'}
    
    except Exception as e:
        logger.error(f"Unexpected error while replacing meal: {e}")
        logger.error(traceback.format_exc())
        return {'status': 'error', 'message': 'An unexpected error occurred during meal replacement.'}
    
    return {
        'status': 'success',
        'message': 'Meal replaced successfully.',
        'replaced_meal': {
            'old_meal': old_meal.name,
            'new_meal': new_meal.name,
            'day': day,
            'meal_type': meal_type
        }
    }


def remove_meal_from_plan(request, meal_plan_id, meal_id, day, meal_type):
    print("From remove_meal_from_plan")
    # Resolve user safely
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'id', None):
        user_id = None
        try:
            data = getattr(request, 'data', None)
            if isinstance(data, dict):
                user_id = data.get('user_id') or data.get('userId') or data.get('id')
        except Exception:
            user_id = None
        if user_id:
            user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            return {'status': 'error', 'message': 'Authenticated user not found. Please ensure you are logged in.'}

    # Retrieve the specified MealPlan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    # Retrieve the specified Meal
    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

    # Validate the day
    if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
        return {'status': 'error', 'message': f'Invalid day: {day}'}
    
    # Validate the meal type
    if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
        return {'status': 'error', 'message': f'Invalid meal type: {meal_type}'}

    # Check if the meal is scheduled for the specified day and meal type in the meal plan
    meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type).first()
    if not meal_plan_meal:
        return {'status': 'error', 'message': 'Meal not scheduled on the specified day and meal type.'}

    # Remove the meal from the meal plan within a transaction to ensure atomicity
    try:
        with transaction.atomic():
            meal_plan_meal.delete()
            meal_plan.has_changes = True
            meal_plan.is_approved = False
            meal_plan.save()
    except Exception as e:
        logger.error(f"Failed to remove meal from plan: {e}")
        return {'status': 'error', 'message': 'Failed to remove meal from the plan.'}
    return {'status': 'success', 'message': 'Meal removed from the plan.'}

def cosine_similarity(vec1, vec2):
    """
    Calculate the cosine similarity between two vectors (lists of floats).
    Uses numpy for the calculation but expects the input vectors as plain lists. 
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    if vec1.shape != vec2.shape:
        raise ValueError("Vectors must have the same length to compute cosine similarity.")
    
    dot_product = np.dot(vec1, vec2)
    magnitude_vec1 = np.linalg.norm(vec1)
    magnitude_vec2 = np.linalg.norm(vec2)
    
    if magnitude_vec1 == 0 or magnitude_vec2 == 0:
        return 0.0
    
    return dot_product / (magnitude_vec1 * magnitude_vec2)


def is_valid_embedding(embedding, expected_length=1536):
    """
    Validate that the embedding is a flat list of floats with the expected length.
    """
    if not isinstance(embedding, list):
        logger.error(f"Embedding is not a list. Type: {type(embedding)}")
        logger.error("Embedding is not a list.")
        return False
    if len(embedding) != expected_length:
        logger.error(f"Embedding length {len(embedding)} does not match expected {expected_length}.")
        return False
    if not all(isinstance(x, float) for x in embedding):
        logger.error("Embedding contains non-float elements.")
        return False
    return True

def create_meal(request=None, user_id=None, name=None, dietary_preferences=None, description=None, meal_type=None, used_pantry_items=None, max_attempts=3, composed_dishes=None):
    from meals.dietary_preferences import assign_dietary_preferences
    attempt = 0

    while attempt < max_attempts:
        try:
            # Step 1: Retrieve the user (prefer authenticated request.user)
            user = None
            if request is not None:
                req_user = getattr(request, 'user', None)
                if req_user and getattr(req_user, 'id', None):
                    user = req_user
                else:
                    # Fallback to request.data
                    data = getattr(request, 'data', None)
                    payload_user_id = None
                    if isinstance(data, dict):
                        payload_user_id = data.get('user_id') or data.get('userId') or data.get('id')
                    if payload_user_id:
                        user = CustomUser.objects.filter(id=payload_user_id).first()
            if user is None and user_id is not None:
                user = CustomUser.objects.filter(id=user_id).first()
            if user is None:
                logger.error("User does not exist or could not be resolved for create_meal.")
                return {'status': 'error', 'message': 'User does not exist'}

            # Generate the user context safely
            try:
                user_context = generate_user_context(user) or 'No additional user context provided.'
            except Exception as e:
                logger.error(f"Error generating user context: {e}")
                user_context = 'No additional user context provided.'



            with transaction.atomic():
                # Step 2: Check for existing meal
                if name:
                    existing_meal = Meal.objects.filter(creator=user, name=name).first()
                    if existing_meal:
                        return {
                            'meal': {
                                'id': existing_meal.id,
                                'name': existing_meal.name,
                                'dietary_preferences': [pref.name for pref in existing_meal.dietary_preferences.all()],
                                'description': existing_meal.description,
                                'created_date': existing_meal.created_date.isoformat(),
                            },
                            'status': 'info',
                            'message': 'A similar meal already exists.',
                            'similar_meal_id': existing_meal.id
                        }


                # Step 3: Generate meal details using GPT, including user context

                # Handle potential None values
                meal_name_input = name or 'Meal Placeholder'
                meal_type_input = meal_type or 'Dinner'
                goal_description = (
                    user.goal.goal_description if hasattr(user, 'goal') and user.goal and user.goal.goal_description
                    else 'No specific goals'
                )
                try:
                    response = get_groq_client().chat.completions.create(
                        model=settings.GROQ_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that generates a meal, its description, and dietary preferences based on information about the user."
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Create the meal '{meal_name_input}', that meets the user's goals of '{goal_description}'. "
                                    f"It is meant to be served as a {meal_type_input} meal. "
                                    f"If available, use pantry items: {used_pantry_items}."
                                    f"Use additional information about the user to help with meal creation: {user_context}"
                                )
                            }
                        ],
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "Meal", 
                                "schema": MealOutputSchema.model_json_schema()
                            }
                        }
                    )

                    # Parse GPT response
                    gpt_output = response.choices[0].message.content
                    meal_data = json.loads(gpt_output)
                    # logger.info(f"Generated meal data: {meal_data}")

                    # Extract meal details
                    meal_name = meal_data.get('meal', {}).get('name', 'Meal Placeholder')
                    description = meal_data.get('meal', {}).get('description', 'Placeholder description')
                    dietary_list = meal_data.get('meal', {}).get('dietary_preferences', [])
                    generated_meal_type = meal_data.get('meal', {}).get('meal_type', 'Dinner')

                except Exception as e:
                    logger.error(f"Error generating meal content: {e}")
                    # Use the input values or placeholders as fallbacks
                    meal_name = meal_name_input
                    description = 'Fallback Description'
                    generated_meal_type = meal_type_input
                    dietary_list = []

                # Step 4: Create and immediately save the Meal instance so it has an ID
                meal = Meal(
                    name=meal_name,
                    creator=user,
                    description=description,
                    meal_type=generated_meal_type,
                    created_date=timezone.now(),
                )
                meal.save()

                # logger.info(f"Meal '{meal.name}' saved successfully with ID {meal.id}.")

                # Step 5: Assign dietary preferences now that the meal has a primary key
                if dietary_list:
                    assign_dietary_preferences(meal.id, dietary_list)

                # Persist composed_dishes if provided (sanitize flags/types)
                if composed_dishes and isinstance(composed_dishes, list) and len(composed_dishes) > 0:
                    sanitized_bundle = []
                    for d in composed_dishes:
                        if not isinstance(d, dict):
                            continue
                        sanitized = {
                            'name': d.get('name', 'Dish'),
                            'dietary_tags': d.get('dietary_tags') or [],
                            'target_groups': d.get('target_groups') or [],
                            'notes': d.get('notes'),
                            'ingredients': d.get('ingredients') or [],
                            # For user-generated meals, force False regardless of model output
                            'is_chef_dish': False,
                        }
                        sanitized_bundle.append(sanitized)
                    meal.composed_dishes = sanitized_bundle
                meal.save()

                # Create structured MealDish rows from composed_dishes (if provided)
                try:
                    if composed_dishes and isinstance(composed_dishes, list):
                        from meals.models import MealDish
                        for d in composed_dishes:
                            MealDish.objects.create(
                                meal=meal,
                                name=d.get('name', 'Dish'),
                                dietary_tags=d.get('dietary_tags') or [],
                                target_groups=d.get('target_groups') or [],
                                notes=d.get('notes'),
                                ingredients=d.get('ingredients'),
                                # Force user-generated composed dishes to non-chef
                                is_chef_dish=False
                            )
                except Exception as e:
                    logger.error(f"Failed to create MealDish rows for meal {meal.id}: {e}")

                # Fetch and assign the custom dietary preferences
                custom_prefs = user.custom_dietary_preferences.all()
                if custom_prefs.exists():
                    meal.custom_dietary_preferences.add(*custom_prefs)
                    logger.info(f"Assigned custom dietary preferences: {[cp.name for cp in custom_prefs]}")


                # Step 6: Generate and assign the embedding
                meal_representation = (
                    f"Name: {meal.name}, Description: {meal.description}, Dietary Preferences: {dietary_list}, "
                    f"Meal Type: {meal.meal_type}, Chef: {user.username}, Price: {meal.price if meal.price else 'N/A'}"
                )
                
                # Try up to 3 times to get a valid embedding
                embedding_attempts = 0
                max_embedding_attempts = 3
                while embedding_attempts < max_embedding_attempts:
                    try:
                        embedding_attempts += 1
                        logger.info(f"Generating embedding for meal '{meal.name}' (attempt {embedding_attempts}/{max_embedding_attempts})")
                        
                        meal_embedding = get_embedding(meal_representation)
                        
                        if meal_embedding and isinstance(meal_embedding, list) and len(meal_embedding) == 1536:
                            meal.meal_embedding = meal_embedding
                            meal.save(update_fields=['meal_embedding'])
                            logger.info(f"Meal embedding assigned successfully for '{meal.name}'.")
                            break
                        else:
                            logger.warning(
                                f"Invalid embedding format for meal '{meal.name}' on attempt {embedding_attempts}. "
                                f"Type: {type(meal_embedding)}, Length: {len(meal_embedding) if meal_embedding else 'None'}"
                            )
                            # Short delay before retrying
                            time.sleep(1)
                    except Exception as e:
                        logger.error(f"Error generating embedding on attempt {embedding_attempts}: {str(e)}")
                        # Short delay before retrying
                        time.sleep(1)
                
                # If we couldn't get a valid embedding after all attempts, create a fallback
                if not hasattr(meal, 'meal_embedding') or meal.meal_embedding is None:
                    logger.warning(f"Using fallback embedding for meal '{meal.name}' after {max_embedding_attempts} failed attempts")
                    # Create a simple fallback embedding (all zeros with a single 1.0 to ensure non-zero magnitude)
                    fallback_embedding = [0.0] * 1536
                    fallback_embedding[0] = 1.0
                    meal.meal_embedding = fallback_embedding
                    meal.save(update_fields=['meal_embedding'])
                    logger.info(f"Fallback embedding assigned for meal '{meal.name}'.")

                # Step 8: Prepare the response
                meal_dict = {
                    'id': meal.id,
                    'name': meal.name,
                    'dietary_preferences': [pref.name for pref in meal.dietary_preferences.all()] or [cp.name for cp in meal.custom_dietary_preferences.all()],
                    'description': meal.description,
                    'meal_type': meal.meal_type,
                    'created_date': meal.created_date.isoformat(),
                    'composed_dishes': meal.composed_dishes,
                }
                return {
                    'meal': meal_dict,
                    'status': 'success',
                    'message': 'Meal created successfully',
                    'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }

        except IntegrityError as e:
            logger.error(f"IntegrityError during meal creation: {e}")
            attempt += 1  # Increment attempt count and retry
        except Exception as e:
            logger.error(f"Unexpected error during meal creation: {e}")
            traceback.print_exc()
            return {'status': 'error', 'message': 'An unexpected error occurred during meal creation.'}

    return {'status': 'error', 'message': 'Maximum attempts reached. Could not create a unique meal.'}

def build_age_safety_note(user) -> str:
    """
    Inspect HouseholdMember records and return a multi‑line string for the prompt.
    •  Babies  < 2 yrs  →  baby‑safe steps (no honey, low salt, puree, no whole nuts…)
    •  Toddlers 2–4 yrs →  small pieces, mild spice
    •  Children 5–11 yrs → kid‑friendly portions
    """
    hm_qs = getattr(user, "household_members", None)
    if hm_qs is None or not hm_qs.exists():
        return ""

    # Get the actual queryset from the RelatedManager
    household_members = hm_qs.all()
    
    babies    : List = [m for m in household_members if m.age and m.age <  2]
    toddlers  : List = [m for m in household_members if m.age and 2 <= m.age < 5]
    children  : List = [m for m in household_members if m.age and 5 <= m.age < 12]

    lines = []
    if babies:
        lines.append(
            f"BABY SAFETY: {len(babies)} baby(ies) <2 yrs – "
            "provide separate baby‑safe prep; no honey, no added salt, no whole nuts, "
            "no raw egg or unpasteurised dairy; puree / mash to age‑appropriate texture."
        )
    if toddlers:
        lines.append(
            f"TODDLER SAFETY: {len(toddlers)} toddler(s) 2‑4 yrs – "
            "cut food into bite‑size pieces, use soft textures, mild spice."
        )
    if children:
        lines.append(
            f"CHILD PREFS: {len(children)} child(ren) 5‑11 yrs – offer kid‑friendly flavours and presentations."
        )

    return "\n".join(lines)

def add_meal_to_plan(request, meal_plan_id, meal_id, day, meal_type, allow_duplicates=False):
    print("From add_meal_to_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

    # Check if the meal can be ordered
    if meal.chef and not meal.can_be_ordered():
        message = f'Meal "{meal.name}" cannot be ordered as it starts tomorrow or earlier. To avoid food waste, chefs need at least 24 hours to plan and prepare the meals.'
        return {
            'status': 'error',
            'message': message
        }

    # Check if the meal's start date falls within the meal plan's week
    if meal.chef and (meal.start_date < meal_plan.week_start_date or meal.start_date > meal_plan.week_end_date):
        return {'status': 'error', 'message': 'Meal not available in the selected week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check if the day is within the meal plan's week
    day_of_week_number = datetime.strptime(day, '%A').weekday()
    target_date = meal_plan.week_start_date + timedelta(days=day_of_week_number)
    if target_date < meal_plan.week_start_date or target_date > meal_plan.week_end_date:
        return {'status': 'error', 'message': 'Invalid day for the meal plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check if there's already a chef-created meal scheduled for that day
    existing_chef_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day, meal__chef__isnull=False).first()
    if existing_chef_meal:
        return {
            'status': 'prompt',
            'message': 'A chef-created meal is already scheduled for this day. Would you like to replace it?',
            'existing_meal': {
                'meal_id': existing_chef_meal.meal.id,
                'name': existing_chef_meal.meal.name,
                'chef': existing_chef_meal.meal.chef.user.username if existing_chef_meal.meal.chef else 'User Created Meal'
            }
        }

    # Check if there's already a meal scheduled for that day
    existing_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day, meal_type=meal_type).first()
    if existing_meal:
        if allow_duplicates:
            # Create a new MealPlanMeal even if a meal is scheduled for that day since duplicates are allowed
            offset = day_to_offset(day)
            meal_date = meal_plan.week_start_date + timedelta(days=offset)

            with transaction.atomic():
                MealPlanMeal.objects.create(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type, meal_date=meal_date)
                meal_plan.has_changes = True
                meal_plan.is_approved = False
                meal_plan.save()
            return {'status': 'success', 'action': 'added_duplicate', 'new_meal': meal.name, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        else:
            # If duplicates are not allowed and a meal is already scheduled, offer to replace it
            return {
                'status': 'prompt',
                'message': 'This day already has a meal scheduled. Would you like to replace it?',
                'existing_meal': {
                    'meal_id': existing_meal.meal.id,
                    'name': existing_meal.meal.name,
                    'chef': existing_meal.meal.chef.user.username if existing_meal.meal.chef else 'User Created Meal'
                }
            }
    else:
        # No existing meal for that day; go ahead and add the new meal
        offset = day_to_offset(day)
        meal_date = meal_plan.week_start_date + timedelta(days=offset)
        with transaction.atomic():
            MealPlanMeal.objects.create(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type, meal_date=meal_date)
            meal_plan.has_changes = True
            meal_plan.is_approved = False
            meal_plan.save()
        return {'status': 'success', 'action': 'added', 'new_meal': meal.name, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def suggest_alternative_meals(request, meal_ids, days_of_week, meal_types):
    """
    Suggest alternative meals based on a list of meal IDs, corresponding days of the week, and meal types.
    Prioritization:
    1) Chef-created meals that match dietary preferences and location for the target date
    2) Auto-generated/user meals (no chef) that match dietary preferences
    """
    # Resolve the user from the authenticated request first; fall back to request.data
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'id', None):
        # Frontend may not send user_id; try to read it, otherwise error out gracefully
        user_id = None
        try:
            data = getattr(request, 'data', None)
            if isinstance(data, dict):
                user_id = data.get('user_id') or data.get('userId') or data.get('id')
        except Exception:
            user_id = None

        if user_id:
            user = CustomUser.objects.filter(id=user_id).first()
        else:
            user = None

        if not user:
            return {'status': 'error', 'message': 'Authenticated user not found. Please ensure you are logged in.'}

    # Safely retrieve or provision a UserRole
    try:
        user_role = UserRole.objects.get(user=user)
    except UserRole.DoesNotExist:
        user_role = UserRole.objects.create(user=user, current_role='customer', is_chef=False)
    
    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    alternative_meals = []
    week_shift = max(int(user.week_shift), 0)  # User's ability to plan for future weeks

    today = timezone.now().date() + timedelta(weeks=week_shift)  # Adjust today's date based on week_shift
    current_weekday = today.weekday()

    # Map of day names to numbers
    day_to_number = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    for meal_id, day_of_week, meal_type in zip(meal_ids, days_of_week, meal_types):

        # Get the day number from the map
        day_of_week_number = day_to_number.get(day_of_week)
        if day_of_week_number is None:
            continue

        days_until_target = (day_of_week_number - current_weekday + 7) % 7
        target_date = today + timedelta(days=days_until_target)

        # 1) Chef-created meals that match dietary preferences AND location for the exact target date
        chef_dietary = Meal.dietary_objects.for_user(user).filter(
            start_date=target_date,
            mealplanmeal__meal_type=meal_type,
        ).exclude(id=meal_id)

        chef_postal = Meal.postal_objects.for_user(user=user).filter(
            start_date=target_date,
            mealplanmeal__meal_type=meal_type,
        ).exclude(id=meal_id)

        chef_available_meals = (chef_dietary & chef_postal).order_by('name')

        # 2) Auto-generated/user meals (no chef) matching dietary preferences and meal type.
        # Do not apply location or date filter, since they are not chef events.
        auto_generated_meals = Meal.dietary_objects.for_user(user).filter(
            chef__isnull=True,
            meal_type=meal_type,
        ).exclude(id=meal_id).order_by('name')

        # Compile meal details with prioritization: chef meals first, then auto-generated
        for meal in list(chef_available_meals) + list(auto_generated_meals):
            start_date_str = meal.start_date.strftime('%Y-%m-%d') if meal.start_date else None
            meal_details = {
                "meal_id": meal.id,
                "name": meal.name,
                "start_date": start_date_str,
                "is_available": meal.can_be_ordered() if hasattr(meal, 'can_be_ordered') else False,
                "chef": (meal.chef.user.username if getattr(meal, 'chef', None) and getattr(meal.chef, 'user', None) else 'User Created Meal'),
                "meal_type": meal_type,
                "is_chef_meal": bool(getattr(meal, 'chef', None)),
            }
            alternative_meals.append(meal_details)

    return {"alternative_meals": alternative_meals}

def replace_meal_based_on_preferences(request, meal_plan_id, old_meal_ids, days_of_week, meal_types):
    logging.info(f"Starting meal replacement for MealPlan ID: {meal_plan_id}")
    
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    
    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        logging.error(f"Meal plan with ID {meal_plan_id} not found for user {user.id}.")
        return {'status': 'error', 'message': 'Meal plan not found.'}

    # Check if the meal plan is linked to a placed order
    if meal_plan.order:
        logging.error(f"Meal plan with ID {meal_plan_id} is associated with a placed order and cannot be modified.")
        return {'status': 'error', 'message': 'Cannot modify a meal plan associated with an order.'}

    replaced_meals = []
    errors = []

    for old_meal_id, day, meal_type in zip(old_meal_ids, days_of_week, meal_types):
        try:
            # Log the current meal being processed
            logging.info(f"Processing meal with ID: {old_meal_id} for {day} - {meal_type}")

            # Validate the existing meal
            old_meal = Meal.objects.get(id=old_meal_id)

            # Validate day and meal type
            if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
                errors.append(f'Invalid day: {day} for meal ID {old_meal_id}')
                continue
            if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
                errors.append(f'Invalid meal type: {meal_type} for meal ID {old_meal_id}')
                continue

            # Check if the meal is scheduled for the specified day and meal type
            meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=old_meal, day=day, meal_type=meal_type).first()
            if not meal_plan_meal:
                errors.append(f'The initial meal with ID {old_meal_id} is not scheduled on {day} and {meal_type}.')
                continue

            # Suggest alternatives or create a new meal based on user preferences and restrictions
            suggested_meals_response = suggest_alternative_meals(request, [old_meal_id], [day], [meal_type])

            if suggested_meals_response['alternative_meals']:
                # If alternatives are found, select the first one as the replacement
                new_meal_id = suggested_meals_response['alternative_meals'][0]['meal_id']
            else:
                # If no alternatives found, create a new meal
                new_meal_response = create_meal(request, name=None, dietary_preference=user.dietary_preferences, description=None, meal_type=meal_type)
                new_meal_id = new_meal_response['meal']['id']

            # Remove the old meal from the plan
            remove_meal_response = remove_meal_from_plan(request, meal_plan_id, old_meal_id, day, meal_type)
            if remove_meal_response['status'] != 'success':
                errors.append(f'Failed to remove the old meal with ID {old_meal_id}.')
                continue

            # Add the new meal to the plan
            with transaction.atomic():
                add_meal_response = add_meal_to_plan(request, meal_plan_id, new_meal_id, day, meal_type)
                if add_meal_response['status'] != 'success':
                    errors.append(f'Failed to add the new meal for {day} and {meal_type}.')
                    continue

                # Collect information about the replaced meal
                replaced_meals.append({
                    'old_meal': old_meal.name,
                    'new_meal_id': new_meal_id,
                    'day': day,
                    'meal_type': meal_type
                })

                # Mark plan changed; require manual approval
                meal_plan.has_changes = True
                meal_plan.is_approved = False
                meal_plan.save()

        except Meal.DoesNotExist:
            logging.error(f"Old meal with ID {old_meal_id} not found.")
            errors.append(f'Old meal with ID {old_meal_id} not found.')
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing meal with ID {old_meal_id}: {str(e)}")
            errors.append(f'An unexpected error occurred while processing meal with ID {old_meal_id}.')

    if errors:
        return {
            'status': 'error',
            'message': 'Some meals could not be replaced.',
            'errors': errors,
            'replaced_meals': replaced_meals
        }
    else:
        return {
            'status': 'success',
            'message': 'All meals replaced successfully.',
            'replaced_meals': replaced_meals
        }

def find_similar_meals(query_vector, threshold=0.1):
    # Find meals with similar embeddings using cosine similarity
    similar_meals = Meal.objects.annotate(
        similarity=CosineDistance(F('meal_embedding'), query_vector)
    ).filter(similarity__lt=threshold)  # Adjust the threshold according to your needs
    
    return similar_meals

def search_meal_ingredients(request, query):
    print("From search_meal_ingredients")
    
    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    
    # Find meals with similar embeddings using cosine similarity
    similar_meals = Meal.objects.annotate(
        similarity=CosineDistance(F('meal_embedding'), query_vector)
    ).filter(similarity__lt=0.1)  # Adjust the threshold according to your needs

    if not similar_meals.exists():
        return {"error": "No meals found matching the query.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    result = []
    for meal in similar_meals:
        meal_ingredients = {
            "meal_id": meal.id,
            "meal_name": meal.name,
            "similarity": meal.similarity,  # Include similarity score in the response
            "dishes": []
        }
        for dish in meal.dishes.all():
            dish_detail = {
                "dish_name": dish.name,
                "ingredients": [ingredient.name for ingredient in dish.ingredients.all()]
            }

            meal_ingredients["dishes"].append(dish_detail)

        result.append(meal_ingredients)

    return {
        "result": result
    }


def auth_search_meals_excluding_ingredient(request, query):
    print("From auth_search_meals_excluding_ingredient")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

   
    # Determine the current date
    week_shift = max(int(user.week_shift), 0)  # Ensure week_shift is not negative
    current_date = timezone.now().date() + timedelta(weeks=week_shift)

    # Find dishes containing the excluded ingredient
    dishes_with_excluded_ingredient = Dish.objects.filter(
        ingredients__name__icontains=query
    ).distinct()

    # Filter meals available for the current week and for the user, excluding those with the unwanted ingredient
    meal_filter_conditions = Q(start_date__gte=current_date)

    # Filter meals by dietary preferences, postal code, and current week
    dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(meal_filter_conditions)
    postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(meal_filter_conditions)

    # Combine both filters
    available_meals = dietary_filtered_meals & postal_filtered_meals
    available_meals = available_meals.exclude(dishes__in=dishes_with_excluded_ingredient)

    # Compile meal details
    meal_details = []
    for meal in available_meals:
        meal_detail = {
            "meal_id": meal.id,
            "name": meal.name,
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.can_be_ordered(),
            "chef": {
                "id": meal.chef.id,
                "name": meal.chef.user.username
            },
            "dishes": [{"id": dish.id, "name": dish.name} for dish in meal.dishes.all()]
        }
        meal_details.append(meal_detail)

    if not meal_details:
        return {
            "message": "No meals found without the specified ingredient for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": meal_details,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def auth_search_ingredients(request, query):
    print("From auth_search_ingredients")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)

    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    # Find similar ingredients based on cosine similarity
    similar_ingredients = Ingredient.objects.annotate(
        similarity=CosineDistance(F('ingredient_embedding'), query_vector)
    ).filter(similarity__lt=0.1)  # Adjust the threshold based on your needs

    # Get IDs of similar ingredients
    similar_ingredient_ids = similar_ingredients.values_list('id', flat=True)

    # Find dishes containing similar ingredients
    dishes_with_similar_ingredients = Dish.objects.filter(ingredients__in=similar_ingredient_ids).distinct()

    # Find meals containing those dishes
    meals_with_similar_ingredients = Meal.objects.filter(dishes__in=dishes_with_similar_ingredients)

    # Prepare the result
    result = []
    for meal in meals_with_similar_ingredients:
        meal_info = {
            'meal_id': meal.id,
            'name': meal.name,
            'start_date': meal.start_date.strftime('%Y-%m-%d'),
            'is_available': meal.can_be_ordered(),
            'chefs': list(meal.chef.values('id', 'user__username')),
            'dishes': list(meal.dishes.values('id', 'name', 'ingredients__id', 'ingredients__name')),
        }
        result.append(meal_info)

    if not result:
        return {
            "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def guest_search_ingredients(request, query, meal_ids=None):
    print("From guest_search_ingredients")
    current_date = timezone.now().date()
    available_meals = Meal.objects.filter(start_date__gte=current_date)

    if meal_ids:
        available_meals = available_meals.filter(id__in=meal_ids)
    
    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    # Find similar ingredients based on cosine similarity
    similar_ingredients = Ingredient.objects.annotate(
        similarity=CosineDistance(F('ingredient_embedding'), query_vector)
    ).filter(similarity__lt=0.1)  # Adjust the threshold based on your needs

    # Get IDs of similar ingredients
    similar_ingredient_ids = similar_ingredients.values_list('id', flat=True)

    # Find dishes containing similar ingredients
    dishes_with_similar_ingredients = Dish.objects.filter(ingredients__in=similar_ingredient_ids).distinct()

    # Find meals containing those dishes
    meals_with_similar_ingredients = Meal.objects.filter(dishes__in=dishes_with_similar_ingredients)

    # Prepare the result
    result = []
    for meal in meals_with_similar_ingredients:
        meal_info = {
            'meal_id': meal.id,
            'name': meal.name,
            'start_date': meal.start_date.strftime('%Y-%m-%d'),
            'is_available': meal.can_be_ordered(),
            'chefs': list(meal.chef.values('id', 'user__username')),
            'dishes': list(meal.dishes.values('id', 'name', 'ingredients__id', 'ingredients__name')),
        }
        result.append(meal_info)

    if not result:
        return {
            "message": "No meals found containing the queried ingredient(s) in the available meals for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def auth_search_chefs(request, query):
    print("From auth_search_chefs")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    # Retrieve user's primary postal code from Address model
    user_addresses = Address.objects.filter(user=user.id)
    user_postal_code = user_addresses[0].normalized_postalcode if user_addresses.exists() else None
    
    # Retrieve chefs based on cosine similarity with the query embedding
    similar_chefs = Chef.objects.annotate(
        similarity=CosineDistance(F('chef_embedding'), query_vector)
    ).filter(similarity__lt=0.1)  # Adjust threshold based on your needs
    # Add additional filters based on user's preferences and location
    if user.dietary_preferences:
        similar_chefs = similar_chefs.filter(meals__dietary_preference=user.dietary_preferences.all())
    if user_postal_code:
        similar_chefs = similar_chefs.filter(serving_postalcodes__code=user_postal_code)
    
    similar_chefs = similar_chefs.distinct()

    auth_chef_result = []
    for chef in similar_chefs:
        featured_dishes = []
        # Retrieve service areas for each chef
        postal_codes_served = chef.serving_postalcodes.values_list('code', flat=True)

        # Check if chef serves user's area
        serves_user_area = user_postal_code in postal_codes_served if user_postal_code else False

        for dish in chef.featured_dishes.all():
            dish_meals = Meal.objects.filter(dishes__id=dish.id)
            dish_info = {
                "id": dish.id,
                "name": dish.name,
                "meals": [
                    {
                        "meal_id": meal.id,
                        "meal_name": meal.name,
                        "start_date": meal.start_date.strftime('%Y-%m-%d'),
                        "is_available": meal.can_be_ordered()
                    }
                    for meal in dish_meals
                ]
            }
            featured_dishes.append(dish_info)

        chef_info = {
            "chef_id": chef.id,
            "name": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
            "featured_dishes": featured_dishes,
            'service_postal_codes': list(postal_codes_served),
            'serves_user_area': serves_user_area,
        }


        auth_chef_result.append(chef_info)

    # # Fetch a suggested meal plan based on the query
    # suggested_meal_plan = auth_get_meal_plan(request, query, 'chef')

    if not auth_chef_result:
        return {
            "message": "No chefs found that match your search.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            # "suggested_meal_plan": suggested_meal_plan
        }
    return {
        "auth_chef_result": auth_chef_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        # "suggested_meal_plan": suggested_meal_plan
    }


def guest_search_chefs(request, query):
    print("From guest_search_chefs")

    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    # Retrieve chefs based on cosine similarity with the query embedding
    similar_chefs = Chef.objects.annotate(
        similarity=CosineDistance(F('chef_embedding'), query_vector)
    ).filter(similarity__lt=0.1).distinct()  # Adjust threshold based on your needs

    guest_chef_result = []
    for chef in similar_chefs:
        featured_dishes = []
        for dish in chef.featured_dishes.all():
            dish_meals = Meal.objects.filter(dishes__id=dish.id)
            dish_info = {
                "id": dish.id,
                "name": dish.name,
                "meals": [
                    {
                        "meal_id": meal.id,
                        "meal_name": meal.name,
                        "start_date": meal.start_date.strftime('%Y-%m-%d'),
                        "is_available": meal.can_be_ordered()
                    } for meal in dish_meals
                ]
            }
            featured_dishes.append(dish_info)

        chef_info = {
            "chef_id": chef.id,
            "name": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
            "featured_dishes": featured_dishes
        }

        # Retrieve service areas for each chef
        postal_codes_served = chef.serving_postalcodes.values_list('code', flat=True)
        chef_info['service_postal_codes'] = list(postal_codes_served)

        guest_chef_result.append(chef_info)

    if not guest_chef_result:
        return {
            "message": "No chefs found matching the query.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    return {
        "guest_chef_result": guest_chef_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def auth_search_dishes(request, query):
    print("From auth_search_dishes")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    
    # Query meals based on postal code and dietary preferences
    week_shift = max(int(user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date__gte=current_date)
    postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date__gte=current_date)
    base_meals = dietary_filtered_meals & postal_filtered_meals
    
    # Retrieve dishes based on cosine similarity with the query embedding
    similar_dishes = Dish.objects.annotate(
        similarity=CosineDistance(F('dish_embedding'), query_vector)
    ).filter(meal__in=base_meals, similarity__lt=0.1).distinct()  # Adjust the threshold based on your needs

    auth_dish_result = []
    for dish in similar_dishes:
        meals_with_dish = set(dish.meal_set.filter(start_date__gte=current_date))
        for meal in meals_with_dish:
            meal_detail = {
                'meal_id': meal.id,
                'name': meal.name,
                'start_date': meal.start_date.strftime('%Y-%m-%d'),
                'is_available': meal.can_be_ordered(),
                'image_url': meal.image.url if meal.image else None,
                'chefs': [{'id': dish.chef.id, 'name': dish.chef.user.username}],
                'dishes': [{'id': dish.id, 'name': dish.name, 'similarity': dish.similarity}],
            }
            auth_dish_result.append(meal_detail)

    if not auth_dish_result:
        return {"message": "No dishes found that match your search.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {"auth_dish_result": auth_dish_result, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def guest_search_dishes(request, query):
    print("From guest_search_dishes")

    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    
    # Retrieve dishes based on cosine similarity with the query embedding
    current_date = timezone.now().date()
    similar_dishes = Dish.objects.annotate(
        similarity=CosineDistance(F('dish_embedding'), query_vector)
    ).filter(similarity__lt=0.1).distinct()  # Adjust threshold based on your needs

    meal_details = defaultdict(lambda: {'name': '', 'chefs': [], 'dishes': []})
    for dish in similar_dishes:
        meals_with_dish = Meal.objects.filter(dishes=dish, start_date__gte=current_date)
        for meal in meals_with_dish:
            meal_details[meal.id].update({
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.can_be_ordered(),
                "chefs": [{"id": dish.chef.id, "name": dish.chef.user.username}],
                "dishes": [{"id": dish.id, "name": dish.name, 'similarity': dish.similarity}]
            })

    guest_dish_result = [{"meal_id": k, **v} for k, v in meal_details.items()]

    if not guest_dish_result:
        return {"message": "No dishes found matching the query.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {"guest_dish_result": guest_dish_result, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def get_or_create_meal_plan(user, start_of_week, end_of_week):
    meal_plan, created = MealPlan.objects.get_or_create(
        user=user,
        week_start_date=start_of_week,
        week_end_date=end_of_week,
        defaults={'created_date': timezone.now()},
    )
    return meal_plan

def cleanup_past_meals(meal_plan, current_date):
    if meal_plan.week_start_date <= current_date <= meal_plan.week_end_date:
        MealPlanMeal.objects.filter(
            meal_plan=meal_plan, 
            day__lt=current_date,
            meal__start_date__lte=current_date  # Only include meals that cannot be ordered
        ).delete()


def auth_get_meal_plan(request):
    print("From auth_get_meal_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)

    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    # ---------- NEW SECTION ----------
    # 1) If the assistant passed a meal_plan_id, use it directly.
    # 2) Otherwise fall back to "current (or shifted) week".
    meal_plan_id = request.data.get('meal_plan_id')
    try:
        if meal_plan_id:
            meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
        else:
            today = timezone.now().date()
            week_shift = int(user.week_shift) 
            start_of_week = today + timedelta(days=-today.weekday(), weeks=week_shift)
            end_of_week   = start_of_week + timedelta(days=6)

            meal_plan = get_or_create_meal_plan(user, start_of_week, end_of_week)

            # Only clean up meals that are in the *current* week
            if week_shift == 0:
                cleanup_past_meals(meal_plan, today)
    except MealPlan.DoesNotExist:
        return {
            'status': 'error',
            'message': 'Meal-plan not found for this user.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    # ---------- END NEW SECTION ----------

    today = timezone.now().date()
    week_shift = int(user.week_shift)   
    start_of_week = today + timedelta(days=-today.weekday(), weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    meal_plan = get_or_create_meal_plan(user, start_of_week, end_of_week)

    if week_shift == 0:
        cleanup_past_meals(meal_plan, today)

    meal_plan_details = [{
        'meal_plan_id': meal_plan.id,
        'week_start_date': meal_plan.week_start_date.strftime('%Y-%m-%d'),
        'week_end_date': meal_plan.week_end_date.strftime('%Y-%m-%d')
    }]

    for meal_plan_meal in MealPlanMeal.objects.filter(meal_plan=meal_plan):
        meal = meal_plan_meal.meal
        chef_username = 'User Created Meal' if meal.creator else (meal.chef.user.username if meal.chef else 'No creator')
        start_date_display = 'User created - No specific date' if meal.creator else (meal.start_date.strftime('%Y-%m-%d') if meal.start_date else 'N/A')
        is_available = 'This meal is user created' if meal.creator else ('Orderable' if meal.can_be_ordered() else 'Not orderable')

        meal_details = {
            "meal_id": meal.id,
            "name": meal.name,
            "chef": chef_username,  # Now indicates 'User Created Meal' if there's a creator
            "start_date": start_date_display,  # Adjusted for user-created meals without a specific date
            "availability": is_available,  # Now includes a specific message for user-created meals
            "dishes": [{"id": dish.id, "name": dish.name} for dish in meal.dishes.all()],
            "day": meal_plan_meal.day,
            "meal_type": meal_plan_meal.meal_type,
            "meal_plan_id": meal_plan.id,
        }
        meal_plan_details.append(meal_details)
    return {
        "auth_meal_plan": meal_plan_details,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def guest_get_meal_plan(request):
    print("From guest_get_meal_plan")

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Start of the week is always Monday
    end_of_week = start_of_week + timedelta(days=6)

    # Define meal types
    meal_types = ['Breakfast', 'Lunch', 'Dinner']

    # Store guest meal plan details
    guest_meal_plan = []
    used_meals = set()

    # Fetch and limit meals for each type, randomizing the selection
    for meal_type in meal_types:
        # Get up to 33 meals of the current type, randomizing using `.order_by('?')`
        possible_meals = Meal.objects.filter(meal_type=meal_type, start_date__gte=today, start_date__lte=end_of_week).order_by('?')[:33]

        if not possible_meals.exists():
            # If no meals available for the specific type, provide a fallback
            fallback_meals = Meal.objects.filter(meal_type=meal_type).order_by('?')[:33]
            possible_meals = fallback_meals

        # Select a subset of meals for the week, ensuring no duplicates across meal types
        for chosen_meal in possible_meals:
            if chosen_meal.id not in used_meals:
                used_meals.add(chosen_meal.id)

                chef_username = chosen_meal.chef.user.username if chosen_meal.chef else 'User Created Meal'
                meal_type = chosen_meal.mealplanmeal_set.first().meal_type if chosen_meal.mealplanmeal_set.exists() else meal_type
                is_available_msg = "Available for exploration - orderable by registered users." if chosen_meal.can_be_ordered() else "Sample meal only."

                # Construct meal details
                meal_details = {
                    "meal_id": chosen_meal.id,
                    "name": chosen_meal.name,
                    "start_date": chosen_meal.start_date.strftime('%Y-%m-%d') if chosen_meal.start_date else "N/A",
                    "is_available": is_available_msg,
                    "dishes": [{"id": dish.id, "name": dish.name} for dish in chosen_meal.dishes.all()],
                    "meal_type": meal_type
                }
                guest_meal_plan.append(meal_details)

    return {
        "guest_meal_plan": guest_meal_plan,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def approve_meal_plan(request, meal_plan_id):
    print("From approve_meal_plan")
    logger.info(f"Approving meal plan with ID: {meal_plan_id}")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return (
                {'status': 'error', 
                 'message': 'Chefs in their chef role are not allowed to use the assistant.'}
            )

        # Step 1: Retrieve the MealPlan using the provided ID
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
        
        # Check if the meal plan is already associated with an order
        if meal_plan.order:
            if meal_plan.order.is_paid:
                # If the order is paid, return a message
                return {
                    'status': 'info', 
                    'message': 'This meal plan has already been paid for.', 
                    'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                # If the order is not paid, return a message
                return {
                    'status': 'info', 
                    'message': 'This meal plan has an unpaid order. Please complete the payment.', 
                    'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }

        # Check if the meal plan requires payment
        paid_meals_exist = False
        for meal_plan_meal in meal_plan.mealplanmeal_set.all():
            meal = meal_plan_meal.meal
            if meal.price and meal.price > 0:
                paid_meals_exist = True
                break
        
        # If no paid meals, approve with no payment
        if not paid_meals_exist:
            meal_plan.is_approved = True
            meal_plan.has_changes = False
            meal_plan.save()
            
            # [1] DETECT IF EXPIRING PANTRY ITEMS WERE USED
            detect_and_trigger_emergency_supply_if_needed(meal_plan, user)

            return {
                'status': 'success', 
                'message': 'Meal plan approved with no payment required.', 
                'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        # Otherwise, create an order for paid meals
        order = Order(customer=user)
        order.save()  # Save to generate an ID

        # Create OrderMeal objects for each meal in the plan
        for meal_plan_meal in meal_plan.mealplanmeal_set.all():
            meal = meal_plan_meal.meal
            if not meal.can_be_ordered():
                continue  # skip if can't be ordered
            if meal.price and meal.price > 0:
                OrderMeal.objects.create(
                    order=order, 
                    meal=meal, 
                    meal_plan_meal=meal_plan_meal, 
                    quantity=1
                )

        # Link the order to the MealPlan
        meal_plan.order = order
        meal_plan.is_approved = True
        meal_plan.has_changes = False
        meal_plan.save()

        # [2] DETECT IF EXPIRING PANTRY ITEMS WERE USED
        detect_and_trigger_emergency_supply_if_needed(meal_plan, user)

        return {
            'status': 'success',
            'message': 'Meal plan approved. Proceed to payment.',
            'order_id': order.id,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        return {
            'status': 'error', 
            'message': f'An unexpected error occurred: {str(e)}'
        }

def detect_and_trigger_emergency_supply_if_needed(meal_plan, user):
    """
    Checks if any bridging usage from this MealPlan references 
    'expiring soon' pantry items, and triggers an emergency supply 
    check if yes.
    """
    from meals.models import MealPlanMealPantryUsage
    from meals.email_service import generate_emergency_supply_list
    
    # Query bridging usage for this meal plan
    bridging_qs = MealPlanMealPantryUsage.objects.filter(
        meal_plan_meal__meal_plan=meal_plan
    )

    # Filter for pantry items that are expiring soon (or already expired).
    # Your logic might vary: maybe you only consider items that are flagged as emergency, 
    # or you also check item_type == 'Dry'/'Canned' etc.
    expiring_usage = bridging_qs.filter(
        pantry_item__expiration_date__isnull=False,
        pantry_item__expiration_date__lte=timezone.now().date() + timedelta(days=7)
    )

    if expiring_usage.exists():
        logger.info(f"[Emergency Supply] {expiring_usage.count()} usage items are from soon-to-expire pantry items!")
        
        # Re-check emergency supply
        generate_emergency_supply_list(user.id)
    else:
        logger.info("[Emergency Supply] No expiring pantry items used. No action needed.")

def analyze_nutritional_content(request, dish_id):
    try:
        dish_id = int(dish_id)
    except ValueError:
        return {'status': 'error', 'message': 'Invalid dish_id'}

    # Retrieving the dish by id
    try:
        dish = Dish.objects.get(pk=dish_id)
    except Dish.DoesNotExist:
        return {'status': 'error', 'message': 'Dish not found'}

    # Preparing the response
    nutritional_content = {
        'calories': dish.calories if dish.calories else 0,
        'fat': dish.fat if dish.fat else 0,
        'carbohydrates': dish.carbohydrates if dish.carbohydrates else 0,
        'protein': dish.protein if dish.protein else 0,
    }

    return {
        'status': 'success',
        'dish_id': dish_id,
        'nutritional_content': nutritional_content
    }


def get_date(request):
    current_time = timezone.now()
    
    # User-friendly formatting
    friendly_date_time = date_format(current_time, "DATETIME_FORMAT")
    day_of_week = date_format(current_time, "l")  # Day name
    
    # Additional date information (optional)
    start_of_week = current_time - timezone.timedelta(days=current_time.weekday())
    end_of_week = start_of_week + timezone.timedelta(days=6)

    return {
        'current_time': friendly_date_time,
        'day_of_week': day_of_week,
        'week_start': start_of_week.strftime('%Y-%m-%d'),
        'week_end': end_of_week.strftime('%Y-%m-%d'),
    }


def sanitize_query(query):
    # Remove delimiters from the user input before executing the query
    return query.replace("####", "")

def standardize_response(status, message, details=None, status_code=200, meal_plan=None):
    """
    Helper function to standardize API responses
    
    Parameters:
    - status: A string indicating the status of the operation (e.g., "success", "error", "existing_plan")
    - message: A user-friendly message describing the result
    - details: Optional dictionary with additional context about the operation
    - status_code: HTTP status code to return
    - meal_plan: Optional MealPlan object to serialize and include in the response
    
    Returns:
    - A Response object with a standardized structure
    """
    from meals.serializers import MealPlanSerializer

    response = {
        "status": status,
        "message": message
    }
    
    if details:
        response["details"] = details
        
    if meal_plan:
        serializer = MealPlanSerializer(meal_plan)
        response["meal_plan"] = serializer.data
        
    return Response(response, status=status_code)

class ChefMealEventPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100
