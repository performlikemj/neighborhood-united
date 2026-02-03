# chefs/services/sous_chef/prompts/__init__.py
"""
Channel-aware prompt system for Sous Chef.
"""

from .builder import build_system_prompt, get_channel_context

__all__ = ["build_system_prompt", "get_channel_context"]
