# chefs/services/sous_chef/__init__.py
"""
Sous Chef Agent - Channel-aware AI assistant for chefs.

Usage:
    from chefs.services.sous_chef import SousChefService
    
    # Web dashboard (full functionality)
    service = SousChefService(chef_id=1, channel="web")
    
    # Telegram (no navigation tools)
    service = SousChefService(chef_id=1, channel="telegram")
    
    # Send message
    result = service.send_message("What orders do I have today?")
"""

from .service import SousChefService
from .agent_factory import SousChefAgentFactory

__all__ = ["SousChefService", "SousChefAgentFactory"]
