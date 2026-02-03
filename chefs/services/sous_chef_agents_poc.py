# chefs/services/sous_chef_agents_poc.py
"""
Sous Chef - OpenAI Agents SDK Proof of Concept

This is a minimal implementation showing how Sous Chef could work with:
- OpenAI Agents SDK for agent orchestration
- LINE MCP Server for LINE messaging integration

To test:
    pip install openai-agents
    npx @line/line-bot-mcp-server  # In another terminal, or let SDK spawn it

Usage:
    from chefs.services.sous_chef_agents_poc import create_sous_chef_agent, run_sous_chef
    
    agent = create_sous_chef_agent(chef_id=1, family_id=123)
    result = await run_sous_chef(agent, "Send a reminder to my LINE about tomorrow's prep")
"""

import os
import asyncio
from typing import Optional, Dict, Any, List

from django.conf import settings

# Agents SDK imports
try:
    from agents import Agent, Runner, function_tool, MCPServerStdio
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    print("⚠️  Install openai-agents: pip install openai-agents")

# Django models (lazy import to avoid circular deps)
def get_chef(chef_id: int):
    from chefs.models import Chef
    return Chef.objects.select_related('user').get(id=chef_id)

def get_family_context(family_id: int, family_type: str) -> dict:
    """Load family context - simplified for POC."""
    from shared.utils import generate_family_context_for_chef
    # Your existing context generation logic
    return {"family_id": family_id, "type": family_type}


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS - Your existing tools, just decorated
# ═══════════════════════════════════════════════════════════════════════════════

if AGENTS_SDK_AVAILABLE:
    
    @function_tool
    def get_family_dietary_preferences(family_id: int) -> Dict[str, Any]:
        """
        Get dietary preferences and restrictions for a family.
        Returns cuisine preferences, allergies, and dietary restrictions.
        """
        # Your existing logic from sous_chef_tools.py
        from customer_dashboard.models import UserPreferences
        from custom_auth.models import CustomUser
        
        try:
            user = CustomUser.objects.get(id=family_id)
            prefs = UserPreferences.objects.filter(user=user).first()
            if prefs:
                return {
                    "dietary_preference": prefs.dietary_preference,
                    "allergies": list(prefs.allergies.values_list('name', flat=True)) if prefs.allergies.exists() else [],
                    "cuisine_preferences": prefs.preferred_cuisines or [],
                }
        except Exception as e:
            return {"error": str(e)}
        
        return {"message": "No preferences found"}

    @function_tool
    def search_chef_dishes(chef_id: int, query: str, limit: int = 5) -> List[Dict]:
        """
        Search dishes in a chef's catalog.
        Returns matching dishes with names, descriptions, and prices.
        """
        # Your existing logic
        from meals.models import Dish
        
        dishes = Dish.objects.filter(
            chef_id=chef_id,
            name__icontains=query
        )[:limit]
        
        return [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description[:100] if d.description else "",
                "price": str(d.price) if d.price else None
            }
            for d in dishes
        ]

    @function_tool
    def get_upcoming_orders(chef_id: int, days: int = 7) -> List[Dict]:
        """
        Get upcoming orders for a chef.
        Returns orders scheduled in the next N days.
        """
        from django.utils import timezone
        from datetime import timedelta
        from meals.models import MealPlanMeal
        
        cutoff = timezone.now() + timedelta(days=days)
        
        # Simplified - adapt to your actual order model
        orders = MealPlanMeal.objects.filter(
            dish__chef_id=chef_id,
            scheduled_date__lte=cutoff,
            scheduled_date__gte=timezone.now()
        ).select_related('dish', 'meal_plan__user')[:20]
        
        return [
            {
                "date": str(o.scheduled_date),
                "dish": o.dish.name if o.dish else "Unknown",
                "customer": o.meal_plan.user.first_name if o.meal_plan and o.meal_plan.user else "Unknown"
            }
            for o in orders
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def create_sous_chef_agent(
    chef_id: int,
    family_id: Optional[int] = None,
    family_type: Optional[str] = None,
    enable_line: bool = False
) -> "Agent":
    """
    Create a Sous Chef agent with optional LINE MCP integration.
    
    Args:
        chef_id: The chef this assistant serves
        family_id: Optional family context
        family_type: 'customer' or 'lead' if family_id provided
        enable_line: Whether to enable LINE MCP server
    
    Returns:
        Configured Agent instance
    """
    if not AGENTS_SDK_AVAILABLE:
        raise ImportError("openai-agents package required. Run: pip install openai-agents")
    
    # Load chef
    chef = get_chef(chef_id)
    chef_name = chef.user.first_name or chef.user.username
    
    # Build context
    context_parts = [f"You are {chef_name}'s personal sous chef assistant."]
    
    if family_id and family_type:
        family_ctx = get_family_context(family_id, family_type)
        context_parts.append(f"Current family context: {family_ctx}")
    
    # Build instructions
    instructions = f"""
{' '.join(context_parts)}

You help {chef_name} with:
- Meal planning and prep guidance
- Understanding family dietary needs and preferences  
- Managing orders and schedules
- Sending notifications to customers via LINE (if enabled)

Be concise, practical, and chef-focused. When sending LINE messages,
keep them professional and friendly.

IMPORTANT: Never include customer health data (allergies, dietary restrictions)
in LINE messages. Only use names and general order info.
"""

    # Build tools list
    tools = [
        get_family_dietary_preferences,
        search_chef_dishes,
        get_upcoming_orders,
    ]
    
    # MCP servers
    mcp_servers = []
    
    if enable_line:
        line_token = getattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN', None) or os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        
        if line_token:
            mcp_servers.append(
                MCPServerStdio(
                    name="line",
                    command="npx",
                    args=["@line/line-bot-mcp-server"],
                    env={
                        "CHANNEL_ACCESS_TOKEN": line_token,
                        # Optionally set a default destination
                        # "DESTINATION_USER_ID": "U...",
                    }
                )
            )
        else:
            print("⚠️  LINE_CHANNEL_ACCESS_TOKEN not set - LINE MCP disabled")
    
    # Create agent
    agent = Agent(
        name=f"Sous Chef ({chef_name})",
        instructions=instructions,
        tools=tools,
        mcp_servers=mcp_servers if mcp_servers else None,
    )
    
    return agent


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def run_sous_chef(agent: "Agent", message: str) -> str:
    """
    Run a single turn with the Sous Chef agent.
    
    Args:
        agent: The configured Sous Chef agent
        message: User message
    
    Returns:
        Agent's response
    """
    result = await Runner.run(agent, message)
    return result.final_output


def run_sous_chef_sync(agent: "Agent", message: str) -> str:
    """Synchronous wrapper for Django views."""
    return Runner.run_sync(agent, message).final_output


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Quick test without Django
    import asyncio
    
    if not AGENTS_SDK_AVAILABLE:
        print("Install openai-agents first: pip install openai-agents")
        exit(1)
    
    # Minimal test agent (no Django models)
    @function_tool
    def get_time() -> str:
        """Get current time."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    test_agent = Agent(
        name="Test Sous Chef",
        instructions="You are a helpful sous chef. Be concise.",
        tools=[get_time],
    )
    
    async def test():
        result = await Runner.run(test_agent, "What time is it?")
        print(f"Response: {result.final_output}")
    
    asyncio.run(test())
