# chefs/services/sous_chef/agent_factory.py
"""
Factory for creating channel-aware Sous Chef agents.
"""

import logging
from typing import Optional, List, Dict, Any

from django.conf import settings

from .tools import get_tool_schemas_for_channel
from .prompts import build_system_prompt, get_channel_context

logger = logging.getLogger(__name__)


class SousChefAgentFactory:
    """
    Factory for creating Sous Chef agents with channel-specific configurations.
    
    Handles:
    - Loading the chef and family context
    - Building channel-appropriate system prompts
    - Filtering tools based on channel capabilities
    - (Future) Configuring MCP servers
    """
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",
        family_id: Optional[int] = None,
        family_type: Optional[str] = None,
    ):
        """
        Initialize the factory.
        
        Args:
            chef_id: ID of the chef this assistant serves
            channel: Channel type ('web', 'telegram', 'line', 'api')
            family_id: Optional family/customer ID for context
            family_type: 'customer' or 'lead' if family_id provided
        """
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
        
        # Load chef
        self._chef = None
        self._customer = None
        self._lead = None
    
    @property
    def chef(self):
        """Lazy load the chef."""
        if self._chef is None:
            from chefs.models import Chef
            self._chef = Chef.objects.select_related('user').get(id=self.chef_id)
        return self._chef
    
    @property
    def chef_name(self) -> str:
        """Get displayable chef name."""
        chef = self.chef
        return (
            getattr(chef, 'chef_nickname', None) or
            chef.user.first_name or
            chef.user.username or
            "Chef"
        )
    
    @property
    def customer(self):
        """Lazy load customer if family_type is 'customer'."""
        if self._customer is None and self.family_type == "customer" and self.family_id:
            from custom_auth.models import CustomUser
            try:
                self._customer = CustomUser.objects.get(id=self.family_id)
            except CustomUser.DoesNotExist:
                pass
        return self._customer
    
    @property
    def lead(self):
        """Lazy load lead if family_type is 'lead'."""
        if self._lead is None and self.family_type == "lead" and self.family_id:
            from crm.models import Lead
            try:
                self._lead = Lead.objects.get(id=self.family_id)
            except Lead.DoesNotExist:
                pass
        return self._lead
    
    def get_family_context(self) -> str:
        """
        Build the family context section for the prompt.
        
        Returns:
            Formatted family context string
        """
        if not self.family_id or not self.family_type:
            return "    <GeneralMode>No specific family selected. Provide general guidance.</GeneralMode>"
        
        try:
            from shared.utils import generate_family_context_for_chef
            
            context = generate_family_context_for_chef(
                chef=self.chef,
                customer=self.customer,
                lead=self.lead,
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Error generating family context: {e}")
            return f"    <Error>Could not load family context: {e}</Error>"
    
    def get_tools_description(self) -> str:
        """
        Build the tools description for the prompt.
        
        Returns:
            Formatted tools description string
        """
        tools = get_tool_schemas_for_channel(self.channel)
        
        lines = []
        for tool in tools:
            name = tool.get("name") or tool.get("function", {}).get("name", "unknown")
            desc = tool.get("description") or tool.get("function", {}).get("description", "")
            lines.append(f"    • {name}: {desc[:100]}...")
        
        return "\n".join(lines)
    
    def build_system_prompt(self) -> str:
        """
        Build the complete system prompt for this configuration.
        
        Returns:
            System prompt string
        """
        return build_system_prompt(
            chef_name=self.chef_name,
            family_context=self.get_family_context(),
            tools_description=self.get_tools_description(),
            channel=self.channel,
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tool schemas for this channel.
        
        Returns:
            List of tool schemas in Groq/OpenAI format
        """
        return get_tool_schemas_for_channel(self.channel)
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get the full context for tool execution.
        
        Returns:
            Dict with chef, customer, lead for tool handlers
        """
        return {
            "chef": self.chef,
            "customer": self.customer,
            "lead": self.lead,
        }
    
    def get_mcp_servers(self) -> List[Any]:
        """
        Get MCP server configurations for this channel.
        
        Returns:
            List of MCP server configs (for future use)
        """
        servers = []
        
        # LINE MCP server for LINE channel
        if self.channel == "line":
            line_token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', None)
            if line_token:
                # Will be implemented when we add Agents SDK
                logger.info("LINE MCP server would be configured here")
        
        return servers
