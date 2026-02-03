# chefs/services/sous_chef/tools/loader.py
"""
Channel-aware tool loader for Sous Chef.

Loads tool schemas and handlers filtered by channel capabilities.
"""

import logging
from typing import List, Dict, Any, Callable, Optional

from .categories import (
    ToolCategory,
    TOOL_REGISTRY,
    get_categories_for_channel,
)

logger = logging.getLogger(__name__)


def _normalize_tool_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a tool schema to OpenAI/Groq format.

    Converts flat format: {"type": "function", "name": "...", ...}
    To nested format: {"type": "function", "function": {"name": "...", ...}}
    """
    # Already in correct format
    if "function" in tool and isinstance(tool.get("function"), dict):
        return tool

    # Convert flat format to nested
    if tool.get("type") == "function" and "name" in tool:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            }
        }

    # Unknown format, return as-is
    return tool


def get_tool_schemas_for_channel(channel: str) -> List[Dict[str, Any]]:
    """
    Get OpenAI-format tool schemas filtered for the given channel.

    Args:
        channel: One of 'web', 'telegram', 'line', 'api'

    Returns:
        List of tool schemas in OpenAI function format
    """
    from meals.sous_chef_tools import SOUS_CHEF_TOOLS

    allowed_categories = get_categories_for_channel(channel)
    filtered_tools = []

    for tool in SOUS_CHEF_TOOLS:
        tool_name = tool.get("name") or tool.get("function", {}).get("name")

        if tool_name is None:
            continue

        category = TOOL_REGISTRY.get(tool_name)

        if category is None:
            # Tool not in registry - include by default (backwards compat)
            logger.warning(f"Tool '{tool_name}' not in registry, including by default")
            filtered_tools.append(_normalize_tool_schema(tool))
        elif category in allowed_categories:
            filtered_tools.append(_normalize_tool_schema(tool))
        else:
            logger.debug(f"Tool '{tool_name}' ({category}) excluded for channel '{channel}'")
    
    logger.info(
        f"Loaded {len(filtered_tools)}/{len(SOUS_CHEF_TOOLS)} tools for channel '{channel}'"
    )
    
    return filtered_tools


def get_tool_handler(tool_name: str) -> Optional[Callable]:
    """
    Get the handler function for a tool.
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        Handler function or None if not found
    """
    from meals.sous_chef_tools import handle_sous_chef_tool_call
    
    # The existing handler dispatches by name
    # We return a wrapper that calls it
    def handler(arguments: Dict[str, Any], **context) -> Dict[str, Any]:
        return handle_sous_chef_tool_call(
            name=tool_name,
            arguments=arguments,
            **context
        )
    
    return handler


def get_tools_for_channel(channel: str) -> Dict[str, Callable]:
    """
    Get tool handlers filtered for the given channel.
    
    Args:
        channel: One of 'web', 'telegram', 'line', 'api'
    
    Returns:
        Dict mapping tool names to handler functions
    """
    allowed_categories = get_categories_for_channel(channel)
    tools = {}
    
    for tool_name, category in TOOL_REGISTRY.items():
        if category in allowed_categories:
            handler = get_tool_handler(tool_name)
            if handler:
                tools[tool_name] = handler
    
    return tools


def get_excluded_tools_message(channel: str) -> str:
    """
    Get a human-readable message about which tools are excluded.
    
    Useful for including in system prompts.
    """
    allowed_categories = get_categories_for_channel(channel)
    excluded = []
    
    for tool_name, category in TOOL_REGISTRY.items():
        if category not in allowed_categories:
            excluded.append(tool_name)
    
    if not excluded:
        return ""
    
    if channel == "telegram":
        return (
            "Note: You're chatting via Telegram. The following UI-specific tools "
            f"are not available: {', '.join(excluded)}. "
            "Guide the chef to use the web dashboard for these actions."
        )
    elif channel == "line":
        return (
            "Note: You're chatting via LINE. The following UI-specific tools "
            f"are not available: {', '.join(excluded)}. "
            "Guide the chef to use the web dashboard for these actions."
        )
    
    return f"Excluded tools for this channel: {', '.join(excluded)}"
