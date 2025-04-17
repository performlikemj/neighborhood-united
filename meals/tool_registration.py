"""
Tool registration system for the OpenAI Responses API integration.

This module brings together all the tools implemented for the meal planning assistant
and provides a unified interface for registering and accessing them.
"""

import logging
from typing import Dict, List, Optional, Any, Union

# Import all tool modules
from .meal_planning_tools import get_meal_planning_tools
from .pantry_management_tools import get_pantry_management_tools
from .chef_connection_tools import get_chef_connection_tools
from .payment_processing_tools import get_payment_processing_tools
from .dietary_preference_tools import get_dietary_preference_tools

# Import all tool implementation functions
from .meal_planning_tools import (
    create_meal_plan,
    modify_meal_plan,
    get_meal_plan,
    generate_meal_instructions
)

from .pantry_management_tools import (
    check_pantry_items,
    add_pantry_item,
    get_expiring_items,
    generate_shopping_list
)

from .chef_connection_tools import (
    find_local_chefs,
    get_chef_details,
    view_chef_meals,
    place_chef_meal_order,
    get_order_details,
    cancel_order
)

from .payment_processing_tools import (
    create_payment_link,
    check_payment_status,
    process_refund
)

from .dietary_preference_tools import (
    manage_dietary_preferences,
    check_meal_compatibility,
    suggest_alternatives
)

logger = logging.getLogger(__name__)

# Dictionary mapping tool names to their implementation functions
TOOL_FUNCTION_MAP = {
    # Meal Planning Tools
    "create_meal_plan": create_meal_plan,
    "modify_meal_plan": modify_meal_plan,
    "get_meal_plan": get_meal_plan,
    "generate_meal_instructions": generate_meal_instructions,
    
    # Pantry Management Tools
    "check_pantry_items": check_pantry_items,
    "add_pantry_item": add_pantry_item,
    "get_expiring_items": get_expiring_items,
    "generate_shopping_list": generate_shopping_list,
    
    # Chef Connection Tools
    "find_local_chefs": find_local_chefs,
    "get_chef_details": get_chef_details,
    "view_chef_meals": view_chef_meals,
    "place_chef_meal_order": place_chef_meal_order,
    "get_order_details": get_order_details,
    "cancel_order": cancel_order,
    
    # Payment Processing Tools
    "create_payment_link": create_payment_link,
    "check_payment_status": check_payment_status,
    "process_refund": process_refund,
    
    # Dietary Preference Tools
    "manage_dietary_preferences": manage_dietary_preferences,
    "check_meal_compatibility": check_meal_compatibility,
    "suggest_alternatives": suggest_alternatives
}

def get_all_tools():
    """
    Get all tools for the OpenAI Responses API.
    
    Returns:
        List of all tools in the format required by the OpenAI Responses API
    """
    all_tools = []
    
    # Add meal planning tools
    all_tools.extend(get_meal_planning_tools())
    
    # Add pantry management tools
    all_tools.extend(get_pantry_management_tools())
    
    # Add chef connection tools
    all_tools.extend(get_chef_connection_tools())
    
    # Add payment processing tools
    all_tools.extend(get_payment_processing_tools())
    
    # Add dietary preference tools
    all_tools.extend(get_dietary_preference_tools())
    
    return all_tools

def get_tools_by_category(category: str):
    """
    Get tools by category for the OpenAI Responses API.
    
    Args:
        category: The category of tools to get (meal_planning, pantry_management, 
                 chef_connection, payment_processing, dietary_preference)
                 
    Returns:
        List of tools in the specified category in the format required by the OpenAI Responses API
    """
    if category == "meal_planning":
        return get_meal_planning_tools()
    elif category == "pantry_management":
        return get_pantry_management_tools()
    elif category == "chef_connection":
        return get_chef_connection_tools()
    elif category == "payment_processing":
        return get_payment_processing_tools()
    elif category == "dietary_preference":
        return get_dietary_preference_tools()
    else:
        logger.warning(f"Unknown tool category: {category}")
        return []

def execute_tool(tool_name: str, **kwargs):
    """
    Execute a tool by name with the provided arguments.
    
    Args:
        tool_name: The name of the tool to execute
        **kwargs: Arguments to pass to the tool function
        
    Returns:
        The result of the tool function execution
    """
    if tool_name not in TOOL_FUNCTION_MAP:
        logger.error(f"Unknown tool: {tool_name}")
        return {
            "status": "error",
            "message": f"Unknown tool: {tool_name}"
        }
        
    try:
        # Get the tool function
        tool_function = TOOL_FUNCTION_MAP[tool_name]
        
        # Execute the tool function with the provided arguments
        result = tool_function(**kwargs)
        
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {
            "status": "error",
            "message": f"Error executing tool {tool_name}: {str(e)}"
        }

def handle_tool_call(tool_call):
    """
    Handle a tool call from the OpenAI Responses API.
    
    Args:
        tool_call: The tool call object from the OpenAI Responses API
        
    Returns:
        The result of the tool function execution
    """
    try:
        # Extract the tool name and arguments
        tool_name = tool_call.function.name
        arguments = tool_call.function.arguments
        
        # Parse the arguments
        import json
        args = json.loads(arguments)
        
        # Execute the tool
        result = execute_tool(tool_name, **args)
        
        return result
    except Exception as e:
        logger.error(f"Error handling tool call: {str(e)}")
        return {
            "status": "error",
            "message": f"Error handling tool call: {str(e)}"
        }
