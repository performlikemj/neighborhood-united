# meals/sous_chef_tools.py
"""
Sous Chef Tools - Chef-specific AI tools for family meal planning.

These tools are designed to help chefs make better decisions when 
planning and preparing meals for the families they serve.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Sum, F

from chefs.models import Chef
from custom_auth.models import CustomUser
from crm.models import Lead, LeadInteraction, LeadHouseholdMember

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (OpenAI Function Schema)
# ═══════════════════════════════════════════════════════════════════════════════

SOUS_CHEF_TOOLS = [
    {
        "type": "function",
        "name": "get_family_dietary_summary",
        "description": "Get a comprehensive summary of all dietary restrictions and allergies for the entire household. Use this to understand what ingredients to avoid and what dietary preferences to honor.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "check_recipe_compliance",
        "description": "Check if a recipe or list of ingredients is safe for this family, considering all dietary restrictions and allergies across household members.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipe_name": {
                    "type": "string",
                    "description": "Name of the recipe or dish"
                },
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ingredients in the recipe"
                }
            },
            "required": ["ingredients"]
        }
    },
    {
        "type": "function",
        "name": "suggest_family_menu",
        "description": "Generate menu suggestions for this family based on their dietary needs, preferences, and order history. Optionally specify the number of days and meal types.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to plan for (default: 7)",
                    "default": 7
                },
                "meal_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Breakfast", "Lunch", "Dinner", "Snack"]
                    },
                    "description": "Which meals to include (default: all)"
                },
                "cuisine_preference": {
                    "type": ["string", "null"],
                    "description": "Optional cuisine style preference (can be null)"
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "scale_recipe_for_household",
        "description": "Calculate scaled ingredient quantities for a recipe based on the household size and optional serving adjustments.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipe_name": {
                    "type": "string",
                    "description": "Name of the recipe"
                },
                "original_servings": {
                    "type": "integer",
                    "description": "Number of servings the original recipe makes"
                },
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"}
                        }
                    },
                    "description": "Original ingredient list with quantities"
                },
                "servings_per_person": {
                    "type": "number",
                    "description": "Servings per household member (default: 1)",
                    "default": 1
                }
            },
            "required": ["recipe_name", "original_servings", "ingredients"]
        }
    },
    {
        "type": "function",
        "name": "get_family_order_history",
        "description": "Retrieve the order history between this chef and this family, including what dishes were ordered and when.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of orders to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "add_family_note",
        "description": "Add a note about this family to the chef's CRM. Use this to record important preferences, feedback, or observations.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the note (max 255 chars)"
                },
                "details": {
                    "type": ["string", "null"],
                    "description": "Full details of the note (can be null)"
                },
                "interaction_type": {
                    "type": ["string", "null"],
                    "enum": ["note", "call", "email", "meeting", "message"],
                    "description": "Type of interaction (default: note, can be null)",
                    "default": "note"
                },
                "next_steps": {
                    "type": ["string", "null"],
                    "description": "Any follow-up actions needed (can be null)"
                }
            },
            "required": ["summary"]
        }
    },
    {
        "type": "function",
        "name": "get_upcoming_family_orders",
        "description": "Get scheduled/upcoming orders for this family.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "estimate_prep_time",
        "description": "Estimate total preparation time for a menu or list of dishes, considering the household size.",
        "parameters": {
            "type": "object",
            "properties": {
                "dishes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "base_prep_minutes": {"type": "integer"},
                            "base_cook_minutes": {"type": "integer"}
                        }
                    },
                    "description": "List of dishes with their base prep/cook times"
                },
                "parallel_cooking": {
                    "type": "boolean",
                    "description": "Whether dishes can be cooked in parallel (default: true)",
                    "default": True
                }
            },
            "required": ["dishes"]
        }
    },
    {
        "type": "function",
        "name": "get_household_members",
        "description": "Get detailed information about each household member, including their individual dietary needs.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "save_family_insight",
        "description": "Save a persistent insight about this family for future reference. Use this when you discover important preferences, tips, things to avoid, or successes that should be remembered across conversations.",
        "parameters": {
            "type": "object",
            "properties": {
                "insight_type": {
                    "type": "string",
                    "enum": ["preference", "tip", "avoid", "success"],
                    "description": "Type of insight: preference (what they like), tip (useful info), avoid (things to not do), success (what worked well)"
                },
                "content": {
                    "type": "string",
                    "description": "The insight to remember (max 500 chars). Be specific and actionable."
                }
            },
            "required": ["insight_type", "content"]
        }
    },
    {
        "type": "function",
        "name": "get_family_insights",
        "description": "Get all saved insights about this family. Use this to recall what you've learned about them.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    # ═══════════════════════════════════════════════════════════════════════════════
    # PREP PLANNING TOOLS
    # ═══════════════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "name": "get_prep_plan_summary",
        "description": "Get a summary of your current prep planning status including active plans, items to purchase today, and overdue items. Use this to understand your upcoming shopping and prep needs.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "generate_prep_plan",
        "description": "Generate a new prep plan for an upcoming date range. This will analyze your upcoming meal shares and service orders, then create an optimized shopping list with timing suggestions based on ingredient shelf life.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to plan for (default: 7, max: 30)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "get_shopping_list",
        "description": "Get your current shopping list from the active prep plan, organized by purchase date or storage category. Shows what to buy when, considering ingredient shelf life and when each ingredient will be used.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_by": {
                    "type": ["string", "null"],
                    "enum": ["date", "category"],
                    "description": "How to organize the list: 'date' groups by when to buy, 'category' groups by storage type (can be null, defaults to date)",
                    "default": "date"
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "get_batch_cooking_suggestions",
        "description": "Get AI-powered batch cooking suggestions to optimize your prep and reduce food waste. Identifies ingredients that appear in multiple meals and can be prepped together.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "check_ingredient_shelf_life",
        "description": "Look up the shelf life and recommended storage for specific ingredients. Useful for planning when to purchase items.",
        "parameters": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ingredient names to check"
                }
            },
            "required": ["ingredients"]
        }
    },
    {
        "type": "function",
        "name": "get_upcoming_commitments",
        "description": "Get all your upcoming meal shares and service orders for the next few days. Useful for understanding what you need to prepare for.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look (default: 7)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "type": "function",
        "name": "lookup_chef_hub_help",
        "description": "Look up detailed documentation about a Chef Hub feature. Use when a chef asks 'how do I...' questions about platform features like profile, services, payment links, meal shares, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The feature or topic to look up (e.g., 'payment links', 'services', 'break mode', 'profile')"
                }
            },
            "required": ["topic"]
        }
    },
    # ═══════════════════════════════════════════════════════════════════════════════
    # NAVIGATION & UI ACTION TOOLS
    # ═══════════════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "name": "navigate_to_dashboard_tab",
        "description": "Navigate the chef to a specific dashboard tab. Use when the chef asks how to do something or wants help with a specific feature. The chef will see a button they can click to navigate.",
        "parameters": {
            "type": "object",
            "properties": {
                "tab": {
                    "type": "string",
                    "enum": ["dashboard", "prep", "profile", "photos", "kitchen", "connections", "clients", "messages", "payments", "services", "meal-shares", "orders", "meals"],
                    "description": "The dashboard tab to navigate to. Note: 'meal-shares' is a sub-tab under 'services'."
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why navigating here helps (shown to the chef)"
                }
            },
            "required": ["tab", "reason"]
        }
    },
    {
        "type": "function",
        "name": "prefill_form",
        "description": "Pre-fill a form with suggested values and navigate to it. Use when helping the chef create something new like a dish, meal, or meal share. The chef will see a button to create the item with pre-filled data.",
        "parameters": {
            "type": "object",
            "properties": {
                "form_type": {
                    "type": "string",
                    "enum": ["ingredient", "dish", "meal", "meal-share", "service"],
                    "description": "Which form to prefill"
                },
                "fields": {
                    "type": "object",
                    "description": "Key-value pairs of field names and suggested values. For ingredient: name, calories, fat, carbohydrates, protein. For dish: name, featured. For meal: name, description, meal_type, price. For meal-share: event_date, event_time, base_price, max_orders. For service: title, description, service_type."
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of the suggestion (shown to the chef)"
                }
            },
            "required": ["form_type", "fields", "reason"]
        }
    },
    {
        "type": "function",
        "name": "scaffold_meal",
        "description": "Generate a complete meal structure with dishes and optionally ingredients using AI. Shows the chef a preview tree that they can edit before creating all items at once. Use when a chef wants to create a new meal and you want to help them quickly scaffold out the entire structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "meal_name": {
                    "type": "string",
                    "description": "Name or hint for the meal (e.g., 'Sunday Soul Food Dinner', 'Italian Date Night')"
                },
                "meal_description": {
                    "type": ["string", "null"],
                    "description": "Optional description for the meal"
                },
                "meal_type": {
                    "type": "string",
                    "enum": ["Breakfast", "Lunch", "Dinner"],
                    "description": "Type of meal (default: Dinner)"
                },
                "include_dishes": {
                    "type": "boolean",
                    "description": "Whether to generate dish suggestions (default: true)"
                },
                "include_ingredients": {
                    "type": "boolean",
                    "description": "Whether to generate ingredient suggestions for each dish (default: false)"
                }
            },
            "required": ["meal_name"]
        }
    }
]


# Tools that require a family/customer context to function
# These will be disabled when no family is selected
FAMILY_REQUIRED_TOOLS = {
    "get_family_dietary_summary",
    "check_recipe_compliance",
    "suggest_family_menu",
    "scale_recipe_for_household",
    "get_family_order_history",
    "add_family_note",
    "get_upcoming_family_orders",
    "get_household_members",
    "save_family_insight",
    "get_family_insights",
    "estimate_prep_time",  # needs household size context
}


def get_sous_chef_tools(include_family_tools: bool = True) -> List[Dict[str, Any]]:
    """
    Return the list of Sous Chef tool definitions in Groq/OpenAI format.
    
    Args:
        include_family_tools: If False, exclude tools that require a family context.
                              Used when chef is using Sous Chef without selecting a family.
    """
    # Transform to the nested function format that Groq expects:
    # {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    formatted_tools = []
    for tool in SOUS_CHEF_TOOLS:
        tool_name = tool["name"]
        
        # Skip family-required tools if not including them
        if not include_family_tools and tool_name in FAMILY_REQUIRED_TOOLS:
            continue
            
        formatted_tools.append({
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        })
    return formatted_tools


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# SOP file mapping for Chef Hub help lookup
SOP_TOPIC_MAP = {
    "profile": "CHEF_PROFILE_GALLERY_SOP.md",
    "gallery": "CHEF_PROFILE_GALLERY_SOP.md",
    "photos": "CHEF_PROFILE_GALLERY_SOP.md",
    "break": "CHEF_PROFILE_GALLERY_SOP.md",
    "stripe": "CHEF_PROFILE_GALLERY_SOP.md",
    "kitchen": "CHEF_KITCHEN_SOP.md",
    "ingredients": "CHEF_KITCHEN_SOP.md",
    "dishes": "CHEF_KITCHEN_SOP.md",
    "services": "CHEF_SERVICES_PRICING_SOP.md",
    "pricing": "CHEF_SERVICES_PRICING_SOP.md",
    "tiers": "CHEF_SERVICES_PRICING_SOP.md",
    "meal-shares": "CHEF_MEAL_SHARES_SOP.md",
    "meal shares": "CHEF_MEAL_SHARES_SOP.md",
    "shared meals": "CHEF_MEAL_SHARES_SOP.md",
    "events": "CHEF_MEAL_SHARES_SOP.md",  # Legacy alias - "Events" renamed to "Meal Shares"
    "meals": "CHEF_MEAL_SHARES_SOP.md",
    "clients": "CHEF_CLIENT_MANAGEMENT_SOP.md",
    "households": "CHEF_CLIENT_MANAGEMENT_SOP.md",
    "connections": "CHEF_CLIENT_MANAGEMENT_SOP.md",  # Connection management is now in Clients tab
    "accept": "CHEF_CLIENT_MANAGEMENT_SOP.md",
    "decline": "CHEF_CLIENT_MANAGEMENT_SOP.md",
    "payment": "CHEF_PAYMENT_LINKS_SOP.md",
    "invoice": "CHEF_PAYMENT_LINKS_SOP.md",
    "prep": "CHEF_PREP_PLANNING_SOP.md",
    "shopping": "CHEF_PREP_PLANNING_SOP.md",
}


def handle_sous_chef_tool_call(
    name: str,
    arguments: str,
    chef: Chef,
    customer: Optional[CustomUser] = None,
    lead: Optional[Lead] = None
) -> Dict[str, Any]:
    """
    Route and execute a sous chef tool call.
    
    Args:
        name: Tool name
        arguments: JSON string of arguments
        chef: The Chef instance
        customer: Optional platform customer
        lead: Optional CRM lead
        
    Returns:
        Tool execution result
    """
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        args = {}
    
    tool_map = {
        "get_family_dietary_summary": _get_family_dietary_summary,
        "check_recipe_compliance": _check_recipe_compliance,
        "suggest_family_menu": _suggest_family_menu,
        "scale_recipe_for_household": _scale_recipe_for_household,
        "get_family_order_history": _get_family_order_history,
        "add_family_note": _add_family_note,
        "get_upcoming_family_orders": _get_upcoming_family_orders,
        "estimate_prep_time": _estimate_prep_time,
        "get_household_members": _get_household_members,
        "save_family_insight": _save_family_insight,
        "get_family_insights": _get_family_insights,
        # Prep planning tools
        "get_prep_plan_summary": _get_prep_plan_summary,
        "generate_prep_plan": _generate_prep_plan,
        "get_shopping_list": _get_shopping_list,
        "get_batch_cooking_suggestions": _get_batch_cooking_suggestions,
        "check_ingredient_shelf_life": _check_ingredient_shelf_life,
        "get_upcoming_commitments": _get_upcoming_commitments_tool,
        # Chef Hub help tool
        "lookup_chef_hub_help": _lookup_chef_hub_help,
        # Navigation & UI action tools
        "navigate_to_dashboard_tab": _navigate_to_dashboard_tab,
        "prefill_form": _prefill_form,
        "scaffold_meal": _scaffold_meal,
    }
    
    handler = tool_map.get(name)
    if not handler:
        return {"status": "error", "message": f"Unknown tool: {name}"}
    
    try:
        return handler(args, chef, customer, lead)
    except Exception as e:
        logger.error(f"Tool {name} error: {e}")
        return {"status": "error", "message": str(e)}


def _lookup_chef_hub_help(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Look up Chef Hub documentation for a topic."""
    import os
    from django.conf import settings
    
    topic = args.get("topic", "").lower()
    
    # Find matching SOP file
    sop_file = None
    for keyword, filename in SOP_TOPIC_MAP.items():
        if keyword in topic:
            sop_file = filename
            break
    
    if not sop_file:
        return {
            "status": "success",
            "content": "No specific documentation found for that topic. Available topics: profile, gallery, photos, kitchen, services, meal shares, meals, clients (including connection management), payment links, prep planning, break mode."
        }
    
    # Read the SOP file
    docs_path = os.path.join(settings.BASE_DIR, "docs", sop_file)
    try:
        with open(docs_path, "r") as f:
            content = f.read()
        
        # Extract relevant section based on topic (simplified: return key sections)
        # For now, return a trimmed version to stay within token limits
        if len(content) > 4000:
            content = content[:4000] + "\n\n[Content trimmed for length...]"
        
        return {
            "status": "success", 
            "source": sop_file,
            "content": content
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"Documentation file not found: {sop_file}"
        }


def _get_family_dietary_summary(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get comprehensive dietary summary for the household."""
    all_restrictions = set()
    all_allergies = set()
    member_details = []
    household_size = 1
    
    if customer:
        household_size = getattr(customer, 'household_member_count', 1)
        
        # Primary contact
        prefs = [p.name for p in customer.dietary_preferences.all()]
        allergies = list(customer.allergies or []) + list(customer.custom_allergies or [])
        
        all_restrictions.update(prefs)
        all_allergies.update(allergies)
        
        member_details.append({
            "name": customer.first_name or customer.username,
            "role": "Primary Contact",
            "dietary_preferences": prefs,
            "allergies": allergies
        })
        
        # Household members
        if hasattr(customer, 'household_members'):
            for member in customer.household_members.all():
                m_prefs = [p.name for p in member.dietary_preferences.all()]
                all_restrictions.update(m_prefs)
                
                member_details.append({
                    "name": member.name,
                    "age": member.age,
                    "dietary_preferences": m_prefs,
                    "notes": member.notes
                })
    
    elif lead:
        household_size = lead.household_size
        
        # Primary contact
        prefs = list(lead.dietary_preferences or [])
        allergies = list(lead.allergies or []) + list(lead.custom_allergies or [])
        
        all_restrictions.update(prefs)
        all_allergies.update(allergies)
        
        member_details.append({
            "name": f"{lead.first_name} {lead.last_name}".strip(),
            "role": "Primary Contact",
            "dietary_preferences": prefs,
            "allergies": allergies
        })
        
        # Household members
        for member in lead.household_members.all():
            m_prefs = list(member.dietary_preferences or [])
            m_allergies = list(member.allergies or []) + list(member.custom_allergies or [])
            
            all_restrictions.update(m_prefs)
            all_allergies.update(m_allergies)
            
            member_details.append({
                "name": member.name,
                "relationship": member.relationship,
                "age": member.age,
                "dietary_preferences": m_prefs,
                "allergies": m_allergies,
                "notes": member.notes
            })
    
    return {
        "status": "success",
        "household_size": household_size,
        "all_dietary_restrictions": sorted(list(all_restrictions)),
        "all_allergies_must_avoid": sorted(list(all_allergies)),
        "member_details": member_details,
        "compliance_note": "Any meal must satisfy ALL listed restrictions and avoid ALL listed allergies."
    }


def _check_recipe_compliance(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Check if a recipe is compliant with family dietary needs."""
    recipe_name = args.get("recipe_name", "Unnamed Recipe")
    ingredients = args.get("ingredients", [])
    
    if not ingredients:
        return {"status": "error", "message": "No ingredients provided"}
    
    # Get family dietary info
    dietary_summary = _get_family_dietary_summary({}, chef, customer, lead)
    
    all_allergies = set(a.lower() for a in dietary_summary.get("all_allergies_must_avoid", []))
    all_restrictions = set(r.lower() for r in dietary_summary.get("all_dietary_restrictions", []))
    
    # Common allergen mappings (simplified)
    allergen_keywords = {
        "peanuts": ["peanut", "groundnut"],
        "tree nuts": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut"],
        "milk": ["milk", "cream", "butter", "cheese", "yogurt", "whey", "casein", "lactose"],
        "egg": ["egg", "mayonnaise", "meringue"],
        "wheat": ["wheat", "flour", "bread", "pasta", "couscous"],
        "soy": ["soy", "tofu", "edamame", "tempeh", "miso"],
        "fish": ["fish", "salmon", "tuna", "cod", "tilapia", "anchovy"],
        "shellfish": ["shrimp", "crab", "lobster", "oyster", "clam", "mussel", "scallop"],
        "sesame": ["sesame", "tahini"],
        "gluten": ["wheat", "barley", "rye", "flour", "bread", "pasta"],
    }
    
    # Diet restriction incompatible ingredients (simplified)
    restriction_conflicts = {
        "vegan": ["meat", "chicken", "beef", "pork", "fish", "egg", "milk", "cheese", "butter", "cream", "honey"],
        "vegetarian": ["meat", "chicken", "beef", "pork", "fish", "bacon", "gelatin"],
        "pescatarian": ["meat", "chicken", "beef", "pork", "bacon"],
        "gluten-free": ["wheat", "flour", "bread", "pasta", "barley", "rye"],
        "dairy-free": ["milk", "cheese", "butter", "cream", "yogurt", "whey"],
        "keto": ["sugar", "bread", "pasta", "rice", "potato", "corn"],
        "halal": ["pork", "bacon", "ham", "lard", "alcohol", "wine"],
        "kosher": ["pork", "shellfish", "mixing dairy and meat"],
    }
    
    issues = []
    warnings = []
    
    ingredients_lower = [i.lower() for i in ingredients]
    
    # Check allergens
    for allergen in all_allergies:
        allergen_lower = allergen.lower()
        keywords = allergen_keywords.get(allergen_lower, [allergen_lower])
        
        for ingredient in ingredients_lower:
            for keyword in keywords:
                if keyword in ingredient:
                    issues.append(f"⚠️ ALLERGEN ALERT: '{ingredient}' may contain {allergen}")
    
    # Check dietary restrictions
    for restriction in all_restrictions:
        restriction_lower = restriction.lower()
        conflicts = restriction_conflicts.get(restriction_lower, [])
        
        for ingredient in ingredients_lower:
            for conflict in conflicts:
                if conflict in ingredient:
                    warnings.append(f"⚡ Dietary conflict: '{ingredient}' may not be compatible with {restriction}")
    
    is_compliant = len(issues) == 0
    
    return {
        "status": "success",
        "recipe_name": recipe_name,
        "is_compliant": is_compliant,
        "allergen_issues": issues,
        "dietary_warnings": warnings,
        "ingredients_checked": len(ingredients),
        "recommendation": "SAFE to prepare" if is_compliant else "DO NOT prepare without modifications"
    }


def _suggest_family_menu(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Suggest menu ideas based on family preferences."""
    days = args.get("days", 7)
    meal_types = args.get("meal_types", ["Breakfast", "Lunch", "Dinner"])
    cuisine_preference = args.get("cuisine_preference")
    
    # Get dietary summary
    dietary_summary = _get_family_dietary_summary({}, chef, customer, lead)
    
    restrictions = dietary_summary.get("all_dietary_restrictions", [])
    allergies = dietary_summary.get("all_allergies_must_avoid", [])
    household_size = dietary_summary.get("household_size", 1)
    
    return {
        "status": "success",
        "message": "Menu suggestion framework ready",
        "parameters": {
            "days_to_plan": days,
            "meal_types": meal_types,
            "household_size": household_size,
            "cuisine_preference": cuisine_preference,
        },
        "constraints": {
            "must_satisfy_diets": restrictions,
            "must_avoid_allergens": allergies,
        },
        "suggestion_note": "Please generate menu suggestions that comply with ALL listed constraints. Each dish should be clearly labeled with which dietary restrictions it satisfies."
    }


def _scale_recipe_for_household(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Scale recipe ingredients for household size."""
    recipe_name = args.get("recipe_name", "Recipe")
    original_servings = args.get("original_servings", 4)
    ingredients = args.get("ingredients", [])
    servings_per_person = args.get("servings_per_person", 1)
    
    # Get household size
    if customer:
        household_size = getattr(customer, 'household_member_count', 1)
    elif lead:
        household_size = lead.household_size
    else:
        household_size = 1
    
    target_servings = household_size * servings_per_person
    scale_factor = target_servings / original_servings if original_servings > 0 else 1
    
    scaled_ingredients = []
    for ing in ingredients:
        scaled = {
            "name": ing.get("name", "Unknown"),
            "original_quantity": ing.get("quantity", 0),
            "scaled_quantity": round(ing.get("quantity", 0) * scale_factor, 2),
            "unit": ing.get("unit", "")
        }
        scaled_ingredients.append(scaled)
    
    return {
        "status": "success",
        "recipe_name": recipe_name,
        "original_servings": original_servings,
        "target_servings": target_servings,
        "household_size": household_size,
        "scale_factor": round(scale_factor, 2),
        "scaled_ingredients": scaled_ingredients
    }


def _get_family_order_history(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get order history for this family with this chef."""
    from chef_services.models import ChefServiceOrder
    from meals.models import ChefMealOrder
    
    limit = args.get("limit", 10)
    orders = []
    
    if customer:
        # Service orders
        service_orders = ChefServiceOrder.objects.filter(
            chef=chef,
            customer=customer,
            status__in=['confirmed', 'completed']
        ).select_related('offering', 'tier').order_by('-created_at')[:limit]
        
        for order in service_orders:
            orders.append({
                "type": "service",
                "date": order.created_at.strftime('%Y-%m-%d'),
                "service": order.offering.title if order.offering else "Service",
                "status": order.status,
                "household_size": order.household_size,
            })
        
        # Meal orders
        meal_orders = ChefMealOrder.objects.filter(
            meal_event__chef=chef,
            customer=customer,
            status__in=['confirmed', 'completed']
        ).select_related('meal_event__meal').order_by('-created_at')[:limit]
        
        for order in meal_orders:
            orders.append({
                "type": "meal_event",
                "date": order.created_at.strftime('%Y-%m-%d'),
                "meal": order.meal_event.meal.name if order.meal_event and order.meal_event.meal else "Meal",
                "quantity": order.quantity,
                "status": order.status,
            })
    
    # Sort combined by date
    orders.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    return {
        "status": "success",
        "total_orders": len(orders),
        "orders": orders[:limit],
        "family_type": "customer" if customer else "lead"
    }


def _add_family_note(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Add a note to the family's CRM record."""
    summary = args.get("summary", "")[:255]
    details = args.get("details", "")
    interaction_type = args.get("interaction_type", "note")
    next_steps = args.get("next_steps", "")
    
    if not summary:
        return {"status": "error", "message": "Summary is required"}
    
    # Find or create lead for this family
    if customer:
        target_lead, _ = Lead.objects.get_or_create(
            owner=chef.user,
            email=customer.email,
            defaults={
                'first_name': customer.first_name or customer.username,
                'last_name': customer.last_name or '',
                'status': Lead.Status.WON,
                'source': Lead.Source.WEB,
            }
        )
    elif lead:
        target_lead = lead
    else:
        return {"status": "error", "message": "No family context available"}
    
    # Create interaction
    interaction = LeadInteraction.objects.create(
        lead=target_lead,
        author=chef.user,
        interaction_type=interaction_type,
        summary=summary,
        details=details,
        next_steps=next_steps,
        happened_at=timezone.now(),
    )
    
    return {
        "status": "success",
        "message": "Note added successfully",
        "note_id": interaction.id,
        "summary": summary,
        "created_at": interaction.created_at.isoformat()
    }


def _get_upcoming_family_orders(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get upcoming orders for this family."""
    from chef_services.models import ChefServiceOrder
    from meals.models import ChefMealOrder
    
    now = timezone.now()
    upcoming = []
    
    if customer:
        # Upcoming service orders
        service_orders = ChefServiceOrder.objects.filter(
            chef=chef,
            customer=customer,
            service_date__gte=now.date(),
            status__in=['draft', 'awaiting_payment', 'confirmed']
        ).select_related('offering').order_by('service_date')
        
        for order in service_orders:
            upcoming.append({
                "type": "service",
                "service_date": order.service_date.isoformat() if order.service_date else None,
                "service_time": order.service_start_time.isoformat() if order.service_start_time else None,
                "service": order.offering.title if order.offering else "Service",
                "status": order.status,
            })
        
        # Upcoming meal events
        meal_orders = ChefMealOrder.objects.filter(
            meal_event__chef=chef,
            customer=customer,
            meal_event__event_date__gte=now.date(),
            status__in=['placed', 'confirmed']
        ).select_related('meal_event__meal').order_by('meal_event__event_date')
        
        for order in meal_orders:
            upcoming.append({
                "type": "meal_event",
                "event_date": order.meal_event.event_date.isoformat() if order.meal_event else None,
                "meal": order.meal_event.meal.name if order.meal_event and order.meal_event.meal else "Meal",
                "quantity": order.quantity,
                "status": order.status,
            })
    
    # Sort by date
    upcoming.sort(key=lambda x: x.get('service_date') or x.get('event_date') or '')
    
    return {
        "status": "success",
        "upcoming_orders": upcoming,
        "total_upcoming": len(upcoming)
    }


def _estimate_prep_time(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Estimate total prep time for dishes."""
    dishes = args.get("dishes", [])
    parallel_cooking = args.get("parallel_cooking", True)
    
    if not dishes:
        return {"status": "error", "message": "No dishes provided"}
    
    # Get household size for scaling
    if customer:
        household_size = getattr(customer, 'household_member_count', 1)
    elif lead:
        household_size = lead.household_size
    else:
        household_size = 1
    
    # Scale factor for larger households (more prep, same cook time)
    prep_scale = 1 + (household_size - 1) * 0.15  # 15% more prep per extra person
    
    total_prep = 0
    total_cook = 0
    max_cook = 0
    
    dish_breakdown = []
    
    for dish in dishes:
        base_prep = dish.get("base_prep_minutes", 15)
        base_cook = dish.get("base_cook_minutes", 30)
        
        scaled_prep = round(base_prep * prep_scale)
        
        dish_breakdown.append({
            "name": dish.get("name", "Dish"),
            "prep_minutes": scaled_prep,
            "cook_minutes": base_cook,
        })
        
        total_prep += scaled_prep
        total_cook += base_cook
        max_cook = max(max_cook, base_cook)
    
    # If parallel cooking, cook time is the longest dish, not sum
    effective_cook = max_cook if parallel_cooking else total_cook
    total_time = total_prep + effective_cook
    
    return {
        "status": "success",
        "household_size": household_size,
        "dishes": dish_breakdown,
        "total_prep_minutes": total_prep,
        "total_cook_minutes": effective_cook,
        "total_time_minutes": total_time,
        "total_time_formatted": f"{total_time // 60}h {total_time % 60}m" if total_time >= 60 else f"{total_time}m",
        "parallel_cooking": parallel_cooking,
        "note": f"Prep time scaled by {round(prep_scale, 2)}x for {household_size} people"
    }


def _get_household_members(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get detailed info about household members."""
    members = []
    
    if customer:
        # Primary contact
        prefs = [p.name for p in customer.dietary_preferences.all()]
        allergies = list(customer.allergies or []) + list(customer.custom_allergies or [])
        
        members.append({
            "name": f"{customer.first_name} {customer.last_name}".strip() or customer.username,
            "role": "Primary Contact",
            "email": customer.email,
            "dietary_preferences": prefs,
            "allergies": allergies,
        })
        
        # Other members
        if hasattr(customer, 'household_members'):
            for member in customer.household_members.all():
                m_prefs = [p.name for p in member.dietary_preferences.all()]
                members.append({
                    "name": member.name,
                    "age": member.age,
                    "dietary_preferences": m_prefs,
                    "notes": member.notes,
                })
    
    elif lead:
        # Primary contact
        prefs = list(lead.dietary_preferences or [])
        allergies = list(lead.allergies or []) + list(lead.custom_allergies or [])
        
        members.append({
            "name": f"{lead.first_name} {lead.last_name}".strip(),
            "role": "Primary Contact",
            "email": lead.email,
            "phone": lead.phone,
            "dietary_preferences": prefs,
            "allergies": allergies,
        })
        
        # Other members
        for member in lead.household_members.all():
            m_prefs = list(member.dietary_preferences or [])
            m_allergies = list(member.allergies or []) + list(member.custom_allergies or [])
            
            members.append({
                "name": member.name,
                "relationship": member.relationship,
                "age": member.age,
                "dietary_preferences": m_prefs,
                "allergies": m_allergies,
                "notes": member.notes,
            })
    
    return {
        "status": "success",
        "total_members": len(members),
        "members": members
    }


def _save_family_insight(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Save a persistent insight about this family."""
    from customer_dashboard.models import FamilyInsight, SousChefThread
    
    insight_type = args.get("insight_type", "preference")
    content = args.get("content", "").strip()
    
    if not content:
        return {"status": "error", "message": "Content is required"}
    
    if len(content) > 500:
        content = content[:500]
    
    valid_types = ["preference", "tip", "avoid", "success"]
    if insight_type not in valid_types:
        return {"status": "error", "message": f"Invalid insight_type. Must be one of: {valid_types}"}
    
    # Find the current active thread (for source_thread reference)
    thread_filter = {'chef': chef, 'is_active': True}
    if customer:
        thread_filter['customer'] = customer
    elif lead:
        thread_filter['lead'] = lead
    
    source_thread = SousChefThread.objects.filter(**thread_filter).first()
    
    # Create the insight
    insight = FamilyInsight.objects.create(
        chef=chef,
        customer=customer,
        lead=lead,
        insight_type=insight_type,
        content=content,
        source_thread=source_thread
    )
    
    # Get family name for response
    family_name = "this family"
    if customer:
        family_name = f"{customer.first_name} {customer.last_name}".strip() or customer.username
    elif lead:
        family_name = f"{lead.first_name} {lead.last_name}".strip()
    
    type_labels = {
        "preference": "Preference",
        "tip": "Useful Tip",
        "avoid": "Thing to Avoid",
        "success": "Success"
    }
    
    return {
        "status": "success",
        "message": f"Saved {type_labels[insight_type].lower()} for {family_name}",
        "insight_id": insight.id,
        "insight_type": insight_type,
        "content": content
    }


def _get_family_insights(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get all saved insights about this family."""
    from customer_dashboard.models import FamilyInsight
    
    # Build filter for this family
    insight_filter = {'chef': chef, 'is_active': True}
    if customer:
        insight_filter['customer'] = customer
        insight_filter['lead__isnull'] = True
    elif lead:
        insight_filter['lead'] = lead
        insight_filter['customer__isnull'] = True
    else:
        return {"status": "error", "message": "No family selected"}
    
    insights = FamilyInsight.objects.filter(**insight_filter).order_by('-created_at')[:20]
    
    # Group by type
    grouped = {
        "preference": [],
        "tip": [],
        "avoid": [],
        "success": []
    }
    
    for insight in insights:
        grouped[insight.insight_type].append({
            "id": insight.id,
            "content": insight.content,
            "created_at": insight.created_at.isoformat()
        })
    
    # Get family name
    family_name = "this family"
    if customer:
        family_name = f"{customer.first_name} {customer.last_name}".strip() or customer.username
    elif lead:
        family_name = f"{lead.first_name} {lead.last_name}".strip()
    
    return {
        "status": "success",
        "family": family_name,
        "total_insights": len(insights),
        "insights_by_type": {
            "preferences": grouped["preference"],
            "tips": grouped["tip"],
            "things_to_avoid": grouped["avoid"],
            "successes": grouped["success"]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PREP PLANNING TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_prep_plan_summary(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get summary of chef's prep planning status."""
    from datetime import date
    from chefs.resource_planning.models import ChefPrepPlan, ChefPrepPlanItem
    
    today = date.today()
    
    # Active plans
    active_plans = ChefPrepPlan.objects.filter(
        chef=chef,
        plan_end_date__gte=today,
        status__in=['generated', 'in_progress']
    )
    active_count = active_plans.count()
    
    # Items to purchase today
    items_today = ChefPrepPlanItem.objects.filter(
        prep_plan__chef=chef,
        prep_plan__status__in=['generated', 'in_progress'],
        suggested_purchase_date=today,
        is_purchased=False
    ).count()
    
    # Overdue items
    items_overdue = ChefPrepPlanItem.objects.filter(
        prep_plan__chef=chef,
        prep_plan__status__in=['generated', 'in_progress'],
        suggested_purchase_date__lt=today,
        is_purchased=False
    ).count()
    
    # Get latest active plan summary
    latest_plan = active_plans.order_by('-plan_start_date').first()
    latest_plan_info = None
    if latest_plan:
        latest_plan_info = {
            "id": latest_plan.id,
            "date_range": f"{latest_plan.plan_start_date} to {latest_plan.plan_end_date}",
            "total_meals": latest_plan.total_meals,
            "total_servings": latest_plan.total_servings,
            "unique_ingredients": latest_plan.unique_ingredients,
            "status": latest_plan.status
        }
    
    return {
        "status": "success",
        "active_plans_count": active_count,
        "items_to_purchase_today": items_today,
        "items_overdue": items_overdue,
        "latest_plan": latest_plan_info,
        "recommendation": (
            "You have overdue shopping items!" if items_overdue > 0
            else f"You have {items_today} items to purchase today." if items_today > 0
            else "Your prep planning is up to date!" if active_count > 0
            else "No active prep plans. Generate one to optimize your shopping."
        )
    }


def _generate_prep_plan(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Generate a new prep plan for the chef."""
    from datetime import date, timedelta
    from chefs.resource_planning.services import generate_prep_plan
    
    days = min(max(args.get("days", 7), 1), 30)  # Clamp between 1-30
    
    today = date.today()
    end_date = today + timedelta(days=days - 1)
    
    try:
        prep_plan = generate_prep_plan(
            chef=chef,
            start_date=today,
            end_date=end_date,
            notes=""
        )
        
        return {
            "status": "success",
            "message": f"Generated prep plan for {days} days",
            "plan_id": prep_plan.id,
            "date_range": f"{prep_plan.plan_start_date} to {prep_plan.plan_end_date}",
            "total_meals": prep_plan.total_meals,
            "total_servings": prep_plan.total_servings,
            "unique_ingredients": prep_plan.unique_ingredients,
            "items_count": prep_plan.items.count(),
            "tip": "Use get_shopping_list to see what to buy and when."
        }
        
    except Exception as e:
        logger.error(f"Failed to generate prep plan: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate prep plan: {str(e)}"
        }


def _get_shopping_list(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get shopping list from the active prep plan."""
    from datetime import date
    from chefs.resource_planning.models import ChefPrepPlan
    from chefs.resource_planning.services import get_shopping_list_by_date, get_shopping_list_by_category
    
    group_by = args.get("group_by", "date")
    today = date.today()
    
    # Get latest active plan
    prep_plan = ChefPrepPlan.objects.filter(
        chef=chef,
        plan_end_date__gte=today,
        status__in=['generated', 'in_progress']
    ).order_by('-plan_start_date').first()
    
    if not prep_plan:
        return {
            "status": "error",
            "message": "No active prep plan found. Use generate_prep_plan to create one."
        }
    
    if group_by == "category":
        shopping_list = get_shopping_list_by_category(prep_plan)
    else:
        shopping_list = get_shopping_list_by_date(prep_plan)
    
    # Count items and summarize
    total_items = sum(len(items) for items in shopping_list.values())
    unpurchased = sum(
        1 for items in shopping_list.values() 
        for item in items 
        if not item.get('is_purchased')
    )
    
    # Format for readability
    formatted_list = {}
    for key, items in shopping_list.items():
        formatted_list[key] = [
            {
                "ingredient": item['ingredient'],
                "quantity": f"{item['quantity']} {item.get('unit', 'units')}",
                "shelf_life": f"{item.get('shelf_life_days', '?')} days",
                "storage": item.get('storage', 'refrigerated'),
                "timing_status": item.get('timing_status', 'unknown'),
                "purchased": item.get('is_purchased', False)
            }
            for item in items
        ]
    
    return {
        "status": "success",
        "plan_id": prep_plan.id,
        "date_range": f"{prep_plan.plan_start_date} to {prep_plan.plan_end_date}",
        "grouped_by": group_by,
        "total_items": total_items,
        "unpurchased_items": unpurchased,
        "shopping_list": formatted_list,
        "tip": (
            "Items are organized by suggested purchase date based on shelf life." if group_by == "date"
            else "Items are organized by storage type (refrigerated, frozen, pantry, counter)."
        )
    }


def _get_batch_cooking_suggestions(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get batch cooking suggestions from the active prep plan."""
    from datetime import date
    from chefs.resource_planning.models import ChefPrepPlan
    
    today = date.today()
    
    # Get latest active plan
    prep_plan = ChefPrepPlan.objects.filter(
        chef=chef,
        plan_end_date__gte=today,
        status__in=['generated', 'in_progress']
    ).order_by('-plan_start_date').first()
    
    if not prep_plan:
        return {
            "status": "error",
            "message": "No active prep plan found. Use generate_prep_plan to create one."
        }
    
    batch_data = prep_plan.batch_suggestions or {}
    suggestions = batch_data.get('suggestions', [])
    tips = batch_data.get('general_tips', [])
    
    return {
        "status": "success",
        "plan_id": prep_plan.id,
        "date_range": f"{prep_plan.plan_start_date} to {prep_plan.plan_end_date}",
        "batch_suggestions": [
            {
                "ingredient": s.get('ingredient'),
                "total_quantity": f"{s.get('total_quantity', 0)} {s.get('unit', 'units')}",
                "suggestion": s.get('suggestion'),
                "prep_day": s.get('prep_day'),
                "meals_covered": s.get('meals_covered', [])
            }
            for s in suggestions
        ],
        "general_tips": tips,
        "summary": f"Found {len(suggestions)} batch cooking opportunities to save time and reduce waste."
    }


def _check_ingredient_shelf_life(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Look up shelf life for ingredients."""
    from chefs.resource_planning.shelf_life import get_ingredient_shelf_lives, get_default_shelf_life
    
    ingredients = args.get("ingredients", [])
    
    if not ingredients:
        return {"status": "error", "message": "No ingredients provided"}
    
    if len(ingredients) > 20:
        ingredients = ingredients[:20]  # Limit to 20
    
    try:
        response = get_ingredient_shelf_lives(ingredients)
        
        results = []
        for ing in response.ingredients:
            results.append({
                "ingredient": ing.ingredient_name,
                "shelf_life_days": ing.shelf_life_days,
                "storage": ing.storage_type,
                "notes": ing.notes
            })
        
        return {
            "status": "success",
            "ingredients": results,
            "tip": "Shelf life assumes proper storage. Refrigerated items should be kept at 35-40°F."
        }
        
    except Exception as e:
        # Fallback to defaults
        logger.warning(f"Shelf life API failed, using defaults: {e}")
        results = []
        for name in ingredients:
            defaults = get_default_shelf_life(name)
            results.append({
                "ingredient": name,
                "shelf_life_days": defaults['shelf_life_days'],
                "storage": defaults['storage_type'],
                "notes": "Estimated based on ingredient category"
            })
        
        return {
            "status": "success",
            "ingredients": results,
            "note": "Using estimated shelf life data"
        }


def _get_upcoming_commitments_tool(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """Get upcoming meal commitments including client meal plans, meal shares, and services."""
    from datetime import date, timedelta
    from chefs.resource_planning.services import get_upcoming_commitments
    
    days = min(max(args.get("days", 7), 1), 30)
    
    today = date.today()
    end_date = today + timedelta(days=days - 1)
    
    commitments = get_upcoming_commitments(chef, today, end_date)
    
    # Count by type
    type_counts = {'client_meal_plan': 0, 'meal_event': 0, 'service_order': 0}
    formatted = []
    for c in commitments:
        type_counts[c.commitment_type] = type_counts.get(c.commitment_type, 0) + 1
        
        type_labels = {
            'client_meal_plan': 'Client Meal Plan',
            'meal_event': 'Meal Share',  # "Events" renamed to "Meal Shares"
            'service_order': 'Service'
        }
        
        formatted.append({
            "type": type_labels.get(c.commitment_type, c.commitment_type),
            "date": c.service_date.isoformat(),
            "meal_name": c.meal_name,
            "servings": c.servings,
            "customer": c.customer_name or None,
            "dishes_count": len(c.dishes)
        })
    
    # Group by date
    by_date = {}
    for c in formatted:
        date_key = c["date"]
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(c)
    
    total_servings = sum(c.servings for c in commitments)
    
    # Build detailed summary
    summary_parts = []
    if type_counts['client_meal_plan'] > 0:
        summary_parts.append(f"{type_counts['client_meal_plan']} client meal plan meals")
    if type_counts['meal_event'] > 0:
        summary_parts.append(f"{type_counts['meal_event']} meal shares")
    if type_counts['service_order'] > 0:
        summary_parts.append(f"{type_counts['service_order']} service appointments")
    
    if summary_parts:
        summary = f"Over the next {days} days, you have: {', '.join(summary_parts)} ({total_servings} total servings)."
    else:
        summary = f"No commitments scheduled for the next {days} days."
    
    return {
        "status": "success",
        "date_range": f"{today} to {end_date}",
        "total_commitments": len(commitments),
        "total_servings": total_servings,
        "breakdown": {
            "client_meal_plans": type_counts['client_meal_plan'],
            "meal_shares": type_counts['meal_event'],
            "service_orders": type_counts['service_order']
        },
        "commitments_by_date": by_date,
        "summary": summary
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION & UI ACTION TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Tab name to display label mapping
TAB_LABELS = {
    "dashboard": "Dashboard",
    "prep": "Prep Planning",
    "profile": "Profile",
    "photos": "Photos",
    "kitchen": "Kitchen",
    "connections": "Connections",
    "clients": "Clients",
    "messages": "Messages",
    "payments": "Payment Links",
    "services": "Services",
    "meal-shares": "Meal Shares",
    "orders": "Orders",
    "meals": "Meals",
}

# Form type to tab mapping
FORM_TAB_MAP = {
    "ingredient": "kitchen",
    "dish": "kitchen",
    "meal": "meals",
    "meal-share": "services",
    "service": "services",
}


def _navigate_to_dashboard_tab(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """
    Navigate the chef to a specific dashboard tab.
    Returns action metadata that the frontend will render as an interactive button.
    """
    tab = args.get("tab", "dashboard")
    reason = args.get("reason", "")
    
    # Validate tab
    if tab not in TAB_LABELS:
        return {
            "status": "error",
            "message": f"Unknown tab: {tab}. Valid tabs: {', '.join(TAB_LABELS.keys())}"
        }
    
    tab_label = TAB_LABELS[tab]
    
    return {
        "status": "success",
        "action_type": "navigate",
        "tab": tab,
        "label": f"Go to {tab_label}",
        "reason": reason,
        "render_as_action": True  # Flag for response builder to render as clickable action
    }


def _prefill_form(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """
    Pre-fill a form with suggested values.
    Returns action metadata that the frontend will render as an interactive button.
    """
    form_type = args.get("form_type", "")
    fields = args.get("fields", {})
    reason = args.get("reason", "")
    
    # Validate form type
    if form_type not in FORM_TAB_MAP:
        return {
            "status": "error",
            "message": f"Unknown form type: {form_type}. Valid types: {', '.join(FORM_TAB_MAP.keys())}"
        }
    
    # Get the destination tab
    target_tab = FORM_TAB_MAP[form_type]
    
    # Create a friendly label
    form_labels = {
        "ingredient": "Ingredient",
        "dish": "Dish",
        "meal": "Meal",
        "meal-share": "Meal Share",
        "service": "Service",
    }
    label = f"Create {form_labels.get(form_type, form_type.title())}"
    
    return {
        "status": "success",
        "action_type": "prefill",
        "form_type": form_type,
        "target_tab": target_tab,
        "fields": fields,
        "label": label,
        "reason": reason,
        "render_as_action": True  # Flag for response builder to render as clickable action
    }


def _scaffold_meal(
    args: Dict[str, Any],
    chef: Chef,
    customer: Optional[CustomUser],
    lead: Optional[Lead]
) -> Dict[str, Any]:
    """
    Generate a meal scaffold with dishes and optionally ingredients.
    Returns the scaffold tree that the frontend will render for preview/editing.
    """
    from meals.scaffold_engine import ScaffoldEngine
    
    meal_name = args.get("meal_name", "")
    meal_description = args.get("meal_description", "")
    meal_type = args.get("meal_type", "Dinner")
    include_dishes = args.get("include_dishes", True)
    include_ingredients = args.get("include_ingredients", False)
    
    if not meal_name:
        return {
            "status": "error",
            "message": "meal_name is required"
        }
    
    try:
        engine = ScaffoldEngine(chef)
        scaffold = engine.generate_scaffold(
            hint=meal_name,
            include_dishes=include_dishes,
            include_ingredients=include_ingredients,
            meal_type=meal_type
        )
        
        # If a description was provided, override the AI-generated one
        if meal_description:
            scaffold.data['description'] = meal_description
        
        return {
            "status": "success",
            "action_type": "scaffold",
            "scaffold": scaffold.to_dict(),
            "render_as_scaffold": True,  # Flag for frontend to render scaffold preview
            "summary": {
                "meal": scaffold.data.get('name'),
                "dish_count": len([c for c in scaffold.children if c.status != 'removed']),
                "ingredient_count": sum(
                    len([i for i in d.children if i.status != 'removed'])
                    for d in scaffold.children if d.status != 'removed'
                )
            }
        }
        
    except Exception as e:
        logger.error(f"Scaffold generation failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate scaffold: {str(e)}"
        }
