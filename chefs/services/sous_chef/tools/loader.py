# chefs/services/sous_chef/tools/loader.py
"""
Channel-aware tool loader for Sous Chef.

Loads tool schemas and handlers filtered by channel capabilities.
Applies sensitive data wrapping for restricted channels.
"""

import logging
from typing import List, Dict, Any, Callable, Optional

from .categories import (
    ToolCategory,
    TOOL_REGISTRY,
    get_categories_for_channel,
)
from .sensitive_wrapper import wrap_sensitive_tool

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


def execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    chef: Any,
    customer: Optional[Any] = None,
    lead: Optional[Any] = None,
    channel: str = "web",
) -> Dict[str, Any]:
    """
    Execute a tool with channel-aware sensitive data handling.
    
    This is the main entry point for tool execution. It:
    1. Checks if the tool is sensitive + channel is restricted
    2. If so, returns a redirect message instead of calling the tool
    3. Otherwise, executes the tool normally
    
    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool
        chef: Chef model instance
        customer: Optional CustomUser instance
        lead: Optional Lead instance
        channel: Current channel (web, telegram, line, api)
    
    Returns:
        Tool result dict. On restricted channels, sensitive tools
        return redirect messages instead of actual data.
    """
    from meals.sous_chef_tools import handle_sous_chef_tool_call
    from .sensitive_wrapper import is_sensitive_tool, is_restricted_channel, get_redirect_message
    import json
    
    # Check if this is a sensitive tool on a restricted channel
    if is_sensitive_tool(tool_name) and is_restricted_channel(channel):
        logger.warning(
            f"Sensitive tool '{tool_name}' blocked on channel '{channel}' "
            f"for chef {getattr(chef, 'id', 'unknown')}"
        )
        
        # Special handling for check_recipe_compliance
        # We want to give a yes/no without details
        if tool_name == "check_recipe_compliance":
            # Call the actual tool to get compliance status
            try:
                result = handle_sous_chef_tool_call(
                    name=tool_name,
                    arguments=json.dumps(args),
                    chef=chef,
                    customer=customer,
                    lead=lead,
                )
                is_compliant = result.get("is_compliant", True)
                has_issues = bool(result.get("issues") or result.get("allergen_issues"))
                
                if is_compliant and not has_issues:
                    return {
                        "status": "success",
                        "is_compliant": True,
                        "channel": channel,
                        "message": (
                            "✅ This recipe appears safe for the family based on their "
                            "dietary profile. For full details, check the dashboard."
                        ),
                    }
                else:
                    return {
                        "status": "restricted",
                        "is_compliant": False,
                        "channel": channel,
                        "message": get_redirect_message(tool_name, channel, compliance_hint="potential issues"),
                        "recommendation": (
                            "⚠️ This recipe may have compliance issues. "
                            "Please check the dashboard for specific details."
                        ),
                    }
            except Exception as e:
                logger.error(f"Error checking compliance: {e}")
                return {
                    "status": "error",
                    "message": "Couldn't check compliance. Please try on the dashboard."
                }
        
        # Default: return redirect message
        return {
            "status": "restricted",
            "channel": channel,
            "tool": tool_name,
            "message": get_redirect_message(tool_name, channel),
        }
    
    # Not sensitive or not restricted - execute normally
    try:
        import json
        return handle_sous_chef_tool_call(
            name=tool_name,
            arguments=json.dumps(args),
            chef=chef,
            customer=customer,
            lead=lead,
        )
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return {
            "status": "error",
            "message": f"Error executing {tool_name}: {str(e)}"
        }
