# chefs/services/sous_chef/__init__.py
"""
Sous Chef Agent - Channel-aware AI assistant for chefs.

Usage:
    from chefs.services.sous_chef import get_sous_chef_service
    
    # Get service (uses feature flag to choose backend)
    service = get_sous_chef_service(chef_id=1, channel="telegram")
    
    # Or use specific implementation:
    from chefs.services.sous_chef import SousChefService  # Groq direct
    from chefs.services.sous_chef import AgentsSousChefService  # Agents SDK
    
    # Send message
    result = service.send_message("What orders do I have today?")
"""

import os
from typing import Optional, Union

from django.conf import settings

from .service import SousChefService
from .agent_factory import SousChefAgentFactory

# Try to import Agents SDK service
try:
    from .agents_service import AgentsSousChefService
    from .agents_factory import AgentsSousChefFactory
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AgentsSousChefService = None
    AgentsSousChefFactory = None
    AGENTS_SDK_AVAILABLE = False


def get_sous_chef_service(
    chef_id: int,
    channel: str = "web",
    family_id: Optional[int] = None,
    family_type: Optional[str] = None,
) -> Union["SousChefService", "AgentsSousChefService"]:
    """
    Factory function to get the appropriate Sous Chef service.
    
    Uses USE_AGENTS_SDK setting or environment variable to determine
    which backend to use.
    
    Args:
        chef_id: ID of the chef
        channel: Channel type ('web', 'telegram', 'line', 'api')
        family_id: Optional family/customer ID
        family_type: 'customer' or 'lead' if family_id provided
    
    Returns:
        SousChefService or AgentsSousChefService instance
    """
    use_agents_sdk = getattr(settings, 'USE_AGENTS_SDK', None)
    if use_agents_sdk is None:
        use_agents_sdk = os.getenv('USE_AGENTS_SDK', 'false').lower() == 'true'
    
    if use_agents_sdk and AGENTS_SDK_AVAILABLE:
        return AgentsSousChefService(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )
    else:
        return SousChefService(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )


__all__ = [
    # Factory function (recommended)
    "get_sous_chef_service",
    # Direct service access
    "SousChefService",
    "SousChefAgentFactory",
    # Agents SDK (if available)
    "AgentsSousChefService",
    "AgentsSousChefFactory",
    "AGENTS_SDK_AVAILABLE",
]
