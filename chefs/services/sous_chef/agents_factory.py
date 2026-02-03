# chefs/services/sous_chef/agents_factory.py
"""
Agents SDK factory for creating Sous Chef agents.

Uses OpenAI Agents SDK with Groq via LiteLLM for the LLM backend.
"""

import logging
import os
from typing import Optional, List, Any

from django.conf import settings

from .prompts.builder import SousChefPromptBuilder
from .tools.categories import get_categories_for_channel

logger = logging.getLogger(__name__)

# Check if Agents SDK is available
try:
    from agents import Agent
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None

# MCPServerStdio may not exist in all versions
try:
    from agents import MCPServerStdio
    MCP_AVAILABLE = True
except ImportError:
    MCPServerStdio = None
    MCP_AVAILABLE = False


def _get_groq_model() -> str:
    """Get the Groq model name for LiteLLM."""
    model = getattr(settings, 'GROQ_MODEL', None) or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
    return f"litellm/groq/{model}"


class AgentsSousChefFactory:
    """
    Factory for creating Sous Chef agents using OpenAI Agents SDK.
    
    Creates channel-aware agents with appropriate tools and instructions.
    Uses Groq via LiteLLM as the LLM backend.
    
    Usage:
        factory = AgentsSousChefFactory(chef_id=1, channel="telegram")
        agent = factory.create_agent()
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
            chef_id: ID of the chef
            channel: Channel type ('web', 'telegram', 'line', 'api')
            family_id: Optional customer/lead ID for family context
            family_type: 'customer' or 'lead' if family_id provided
        """
        if not AGENTS_SDK_AVAILABLE:
            raise ImportError(
                "OpenAI Agents SDK not installed. "
                "Run: pip install 'openai-agents[litellm]>=0.6.0'"
            )
        
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
        
        # Lazy load chef
        self._chef = None
        self._customer = None
        self._lead = None
    
    @property
    def chef(self):
        """Lazy load chef model."""
        if self._chef is None:
            from chefs.models import Chef
            self._chef = Chef.objects.select_related('user').get(id=self.chef_id)
        return self._chef
    
    @property
    def customer(self):
        """Lazy load customer if family_type is customer."""
        if self._customer is None and self.family_type == "customer" and self.family_id:
            from custom_auth.models import CustomUser
            try:
                self._customer = CustomUser.objects.get(id=self.family_id)
            except CustomUser.DoesNotExist:
                pass
        return self._customer
    
    @property
    def lead(self):
        """Lazy load lead if family_type is lead."""
        if self._lead is None and self.family_type == "lead" and self.family_id:
            from crm.models import Lead
            try:
                self._lead = Lead.objects.get(id=self.family_id)
            except Lead.DoesNotExist:
                pass
        return self._lead
    
    def create_agent(self) -> "Agent":
        """
        Create a configured Sous Chef agent.
        
        Returns:
            Agent instance configured for the channel with appropriate
            tools, instructions, and model.
        """
        return Agent(
            name=self._get_agent_name(),
            instructions=self._build_instructions(),
            model=_get_groq_model(),
            tools=self._get_tools(),
            mcp_servers=self._get_mcp_servers(),
        )
    
    def _get_agent_name(self) -> str:
        """Get the agent's display name."""
        chef_name = self.chef.user.first_name or self.chef.user.username
        return f"Sous Chef ({chef_name})"
    
    def _build_instructions(self) -> str:
        """Build channel-aware system instructions."""
        builder = SousChefPromptBuilder(
            chef=self.chef,
            channel=self.channel,
            customer=self.customer,
            lead=self.lead,
        )
        return builder.build()
    
    def _get_tools(self) -> List[Any]:
        """Get channel-appropriate tools as function_tools."""
        from .tools.agents_tools import get_tools_for_agents
        return get_tools_for_agents(
            channel=self.channel,
            chef=self.chef,
            customer=self.customer,
            lead=self.lead,
        )
    
    def _get_mcp_servers(self) -> Optional[List[Any]]:
        """Get MCP servers for this channel."""
        if not MCP_AVAILABLE:
            return None
        
        servers = []
        
        # LINE MCP server for LINE channel
        if self.channel == "line":
            line_server = self._create_line_mcp()
            if line_server:
                servers.append(line_server)
        
        return servers if servers else None
    
    def _create_line_mcp(self) -> Optional[Any]:
        """Create LINE MCP server if configured."""
        if not MCP_AVAILABLE or MCPServerStdio is None:
            return None
        
        line_token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', None) or \
                     os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        
        if not line_token:
            logger.warning("LINE_CHANNEL_ACCESS_TOKEN not set - LINE MCP disabled")
            return None
        
        return MCPServerStdio(
            name="line",
            command="npx",
            args=["@line/line-bot-mcp-server"],
            env={
                "CHANNEL_ACCESS_TOKEN": line_token,
            }
        )
    
    def get_context(self) -> dict:
        """Get context dict for tool execution."""
        return {
            "chef": self.chef,
            "customer": self.customer,
            "lead": self.lead,
        }
