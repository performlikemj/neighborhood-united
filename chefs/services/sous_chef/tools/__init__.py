# chefs/services/sous_chef/tools/__init__.py
"""
Channel-aware tool system for Sous Chef.

Tools are categorized by where they can be used:
- CORE: Available on all channels (queries, data retrieval)
- SENSITIVE: Health/PII data - wrapped on restricted channels
- NAVIGATION: Web dashboard only (UI navigation, form prefills)
- MESSAGING: Messaging channels (draft messages for customers)

Security:
- SENSITIVE tools return redirect messages on Telegram/LINE
- This is a defense-in-depth measure (not relying on LLM compliance)
"""

from .categories import (
    ToolCategory, 
    TOOL_REGISTRY, 
    CHANNEL_TOOLS,
    SENSITIVE_RESTRICTED_CHANNELS,
)
from .loader import (
    get_tools_for_channel, 
    get_tool_schemas_for_channel,
    execute_tool,
)
from .sensitive_wrapper import (
    is_sensitive_tool,
    is_restricted_channel,
    wrap_sensitive_tool,
)

__all__ = [
    # Categories
    "ToolCategory",
    "TOOL_REGISTRY", 
    "CHANNEL_TOOLS",
    "SENSITIVE_RESTRICTED_CHANNELS",
    # Loader
    "get_tools_for_channel",
    "get_tool_schemas_for_channel",
    "execute_tool",
    # Sensitive wrapper
    "is_sensitive_tool",
    "is_restricted_channel",
    "wrap_sensitive_tool",
]
