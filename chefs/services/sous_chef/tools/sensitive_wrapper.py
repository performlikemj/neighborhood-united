# chefs/services/sous_chef/tools/sensitive_wrapper.py
"""
Sensitive data wrapper for channel-aware tool execution.

Wraps sensitive tools to enforce channel-based restrictions.
On restricted channels (Telegram, LINE), sensitive tools return
redirect messages instead of actual data.

This is a defense-in-depth measure - we don't rely solely on
the LLM following prompt instructions.
"""

import logging
from typing import Callable, Dict, Any, Optional

from .categories import (
    ToolCategory,
    TOOL_REGISTRY,
    SENSITIVE_RESTRICTED_CHANNELS,
)

logger = logging.getLogger(__name__)


# Redirect messages for each sensitive tool
# These tell the user where to find the data instead
SENSITIVE_REDIRECT_MESSAGES: Dict[str, str] = {
    "get_family_dietary_summary": (
        "🔒 For privacy, I can't share dietary details or allergies over {channel}. "
        "Please check the dashboard: go to your client's profile → Dietary Info. "
        "Or ask me again when you're using the web app!"
    ),
    "get_household_members": (
        "🔒 Household member details (including dietary info) aren't available over {channel}. "
        "View them on the dashboard: Client Profile → Household Members. "
        "I can help with other questions here though!"
    ),
    "check_recipe_compliance": (
        "🔒 I can't share specific allergy details over {channel}. "
        "For a full compliance check with names and specific allergens, "
        "please use the web dashboard. I can tell you the recipe has "
        "{compliance_hint} - check the dashboard for details."
    ),
    "suggest_ingredient_substitution": (
        "🔒 Substitution suggestions reference specific allergies, which I can't share over {channel}. "
        "Please check the dashboard for personalized substitution advice, "
        "or tell me the specific restriction and I can give general guidance."
    ),
}

# Default message for any sensitive tool not explicitly listed
DEFAULT_REDIRECT_MESSAGE = (
    "🔒 This information contains sensitive data that I can't share over {channel}. "
    "Please check the web dashboard for full details."
)


def is_sensitive_tool(tool_name: str) -> bool:
    """Check if a tool is in the SENSITIVE category."""
    return TOOL_REGISTRY.get(tool_name) == ToolCategory.SENSITIVE


def is_restricted_channel(channel: str) -> bool:
    """Check if a channel restricts sensitive data."""
    return channel in SENSITIVE_RESTRICTED_CHANNELS


def get_redirect_message(tool_name: str, channel: str, **kwargs) -> str:
    """Get the redirect message for a sensitive tool on a restricted channel."""
    template = SENSITIVE_REDIRECT_MESSAGES.get(tool_name, DEFAULT_REDIRECT_MESSAGE)
    return template.format(channel=channel, **kwargs)


def wrap_sensitive_tool(
    original_fn: Callable,
    tool_name: str,
    channel: str,
) -> Callable:
    """
    Wrap a tool function with sensitive data checking.
    
    If the tool is sensitive AND the channel is restricted,
    returns a wrapped function that returns a redirect message.
    
    Otherwise, returns the original function unchanged.
    
    Args:
        original_fn: The original tool implementation function
        tool_name: Name of the tool (for looking up category)
        channel: Current channel (web, telegram, line, etc.)
    
    Returns:
        Either the original function or a wrapped version that
        returns redirect messages on restricted channels.
    """
    # If not sensitive or not restricted channel, pass through
    if not is_sensitive_tool(tool_name):
        return original_fn
    
    if not is_restricted_channel(channel):
        return original_fn
    
    # Log that we're wrapping this tool
    logger.info(
        f"Wrapping sensitive tool '{tool_name}' for channel '{channel}'"
    )
    
    # Special handling for check_recipe_compliance
    # We want to give a yes/no answer without exposing names
    if tool_name == "check_recipe_compliance":
        return _create_compliance_wrapper(original_fn, channel)
    
    # Default: return redirect message
    def wrapped_fn(
        args: Dict[str, Any],
        chef: Any,
        customer: Optional[Any],
        lead: Optional[Any],
    ) -> Dict[str, Any]:
        """Wrapped function that returns redirect instead of data."""
        logger.warning(
            f"Sensitive tool '{tool_name}' blocked on channel '{channel}' "
            f"for chef {getattr(chef, 'id', 'unknown')}"
        )
        
        return {
            "status": "restricted",
            "channel": channel,
            "tool": tool_name,
            "message": get_redirect_message(tool_name, channel),
        }
    
    return wrapped_fn


def _create_compliance_wrapper(
    original_fn: Callable,
    channel: str,
) -> Callable:
    """
    Special wrapper for check_recipe_compliance.
    
    Calls the original function but sanitizes the response
    to remove names and specific allergy references.
    Returns just compliance status + generic message.
    """
    def wrapped_compliance(
        args: Dict[str, Any],
        chef: Any,
        customer: Optional[Any],
        lead: Optional[Any],
    ) -> Dict[str, Any]:
        """Compliance check that hides sensitive details."""
        # Call original to get actual compliance status
        try:
            result = original_fn(args, chef, customer, lead)
        except Exception as e:
            logger.error(f"Error in compliance check: {e}")
            return {
                "status": "error",
                "message": "Couldn't check compliance. Please try on the dashboard."
            }
        
        # Extract just the compliance status
        is_compliant = result.get("is_compliant", True)
        has_issues = bool(result.get("issues") or result.get("allergen_issues"))
        
        if is_compliant and not has_issues:
            compliance_hint = "no issues detected"
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
            compliance_hint = "potential issues"
            return {
                "status": "restricted",
                "is_compliant": False,
                "channel": channel,
                "message": get_redirect_message(
                    "check_recipe_compliance", 
                    channel,
                    compliance_hint=compliance_hint
                ),
                "recommendation": (
                    "⚠️ This recipe may have compliance issues. "
                    "Please check the dashboard for specific details about "
                    "which ingredients may be problematic."
                ),
            }
    
    return wrapped_compliance


def create_wrapped_tool_executor(
    tool_executors: Dict[str, Callable],
    channel: str,
) -> Dict[str, Callable]:
    """
    Create a dictionary of tool executors with sensitive tools wrapped.
    
    Args:
        tool_executors: Dict mapping tool names to their executor functions
        channel: Current channel for determining wrapping behavior
    
    Returns:
        New dict with sensitive tools wrapped for the channel
    """
    wrapped = {}
    
    for tool_name, executor in tool_executors.items():
        wrapped[tool_name] = wrap_sensitive_tool(executor, tool_name, channel)
    
    return wrapped
