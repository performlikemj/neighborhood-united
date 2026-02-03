# chefs/services/sous_chef/tools/__init__.py
"""
Channel-aware tool system for Sous Chef.

Tools are categorized by where they can be used:
- CORE: Available on all channels (queries, data retrieval)
- NAVIGATION: Web dashboard only (UI navigation, form prefills)
- MESSAGING: Messaging channels (draft messages for customers)
"""

from .categories import ToolCategory, TOOL_REGISTRY, CHANNEL_TOOLS
from .loader import get_tools_for_channel, get_tool_schemas_for_channel

__all__ = [
    "ToolCategory",
    "TOOL_REGISTRY", 
    "CHANNEL_TOOLS",
    "get_tools_for_channel",
    "get_tool_schemas_for_channel",
]
