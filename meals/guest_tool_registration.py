"""
guest_tool_registration.py

Defines a subset of tools available to guest users, along with helper functions
for retrieving their metadata and callables.
"""

import json
from meals.tool_registration import get_all_tools, handle_tool_call
from shared.utils import (
    guest_search_dishes,
    guest_search_chefs,
    guest_get_meal_plan,
    guest_search_ingredients,
)
from local_chefs.views import chef_service_areas

# Mapping of guest-only tool names to their implementation functions
guest_functions = {
    "guest_search_dishes": guest_search_dishes,
    "guest_search_chefs": guest_search_chefs,
    "guest_get_meal_plan": guest_get_meal_plan,
    "guest_search_ingredients": guest_search_ingredients,
    "chef_service_areas": chef_service_areas,
}

def get_guest_tool_definitions():
    """
    Return only the tool definitions for guest user functions.
    """
    return [tool for tool in get_all_tools() if tool.get("name") in guest_functions]


def get_guest_tool_registry(request):
    """
    Return a dict mapping tool names to callables that invoke the underlying
    function with the current request and arguments.
    """
    registry = {}
    for name, func in guest_functions.items():
        # Bind each function to the request context
        registry[name] = (lambda f: lambda **kwargs: f(request, **kwargs))(func)
    return registry


def handle_guest_tool_call(tool_call, request):
    """
    Route a tool call object to the appropriate guest function.

    Args:
        tool_call: An object with 'function.name' and 'function.arguments'.
        request: Django request object.
    Returns:
        The result of the guest function execution.
    """
    # Extract name and parse arguments
    name = tool_call.function.name
    args = tool_call.function.arguments
    # Parse JSON arguments if needed
    if isinstance(args, str):
        args = json.loads(args)

    func = guest_functions.get(name)
    if not func:
        raise ValueError(f"Unknown guest tool: {name}")

    # Call the function with request and parsed arguments
    return func(request, **args)
