# Sous Chef Agent Refactor Plan

## Overview

Migrate Sous Chef from direct Groq API calls to OpenAI Agents SDK for:
- Channel-aware tool loading (web vs telegram)
- MCP support (LINE, future integrations)
- Built-in agent loop, streaming, tracing
- Cleaner tool management

## Current State

```
meals/sous_chef_assistant.py    # Main implementation (Groq API)
meals/sous_chef_tools.py        # Tool definitions
meals/sous_chef_suggestions.py  # Proactive suggestions
chefs/services/sous_chef_agents_poc.py  # Agents SDK POC
```

**Current flow:**
```
Request → SousChefAssistant → Groq API → Tool calls → Response
                  ↓
        SousChefThread (Django model for history)
```

## Target Architecture

```
Request → SousChefAgentFactory → Agent (with channel-specific tools)
                                    ↓
                              Runner.run() / Runner.run_sync()
                                    ↓
                              MCP Servers (LINE, etc.)
                                    ↓
                              Response + Thread persistence
```

---

## Phase 1: Channel-Aware Tool System

### 1.1 Define Tool Categories

```python
# tools/categories.py

class ToolCategory:
    # Available everywhere
    CORE = "core"
    # Web dashboard only
    NAVIGATION = "navigation"
    # Messaging channels (Telegram, LINE)
    MESSAGING = "messaging"
    # MCP-based tools
    MCP = "mcp"

TOOL_REGISTRY = {
    # Core tools - all channels
    "get_family_dietary_preferences": ToolCategory.CORE,
    "search_chef_dishes": ToolCategory.CORE,
    "get_upcoming_orders": ToolCategory.CORE,
    "get_chef_schedule": ToolCategory.CORE,
    "search_recipes": ToolCategory.CORE,
    
    # Navigation - web only
    "navigate_to_tab": ToolCategory.NAVIGATION,
    "prefill_form": ToolCategory.NAVIGATION,
    "show_scaffold_preview": ToolCategory.NAVIGATION,
    
    # Messaging - Telegram/LINE
    "send_notification": ToolCategory.MESSAGING,
}

CHANNEL_ALLOWED_CATEGORIES = {
    "web": [ToolCategory.CORE, ToolCategory.NAVIGATION],
    "telegram": [ToolCategory.CORE, ToolCategory.MESSAGING],
    "line": [ToolCategory.CORE, ToolCategory.MESSAGING, ToolCategory.MCP],
}
```

### 1.2 Tool Loader

```python
# tools/loader.py

def get_tools_for_channel(channel: str) -> list:
    """Load tools appropriate for the channel."""
    allowed_categories = CHANNEL_ALLOWED_CATEGORIES.get(channel, [ToolCategory.CORE])
    
    tools = []
    for tool_name, category in TOOL_REGISTRY.items():
        if category in allowed_categories:
            tools.append(load_tool(tool_name))
    
    return tools
```

---

## Phase 2: Agent Factory

### 2.1 Main Factory

```python
# services/sous_chef_agent.py

from agents import Agent, Runner, MCPServerStdio

class SousChefAgentFactory:
    """Factory for creating channel-aware Sous Chef agents."""
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",  # web | telegram | line
        family_id: int = None,
        family_type: str = None,
    ):
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
        self.chef = self._load_chef()
    
    def create_agent(self) -> Agent:
        """Create configured agent for this channel."""
        return Agent(
            name=f"Sous Chef ({self.chef.display_name})",
            instructions=self._build_instructions(),
            tools=self._get_tools(),
            mcp_servers=self._get_mcp_servers(),
        )
    
    def _build_instructions(self) -> str:
        """Build channel-aware system prompt."""
        base = self._load_base_prompt()
        
        if self.channel == "telegram":
            base += """
            
## Telegram Context
You're chatting via Telegram. You CANNOT:
- Navigate the dashboard (user isn't looking at it)
- Prefill forms or show previews
- Use UI-specific features

Instead, provide information conversationally and suggest they
visit the dashboard for actions requiring the UI.
"""
        elif self.channel == "line":
            base += """
            
## LINE Context  
You can send LINE messages to customers using the LINE tools.
Keep messages professional, friendly, and concise.
NEVER include health/dietary data in LINE messages.
"""
        
        return base
    
    def _get_tools(self) -> list:
        """Get channel-appropriate tools."""
        return get_tools_for_channel(self.channel)
    
    def _get_mcp_servers(self) -> list:
        """Get MCP servers for this channel."""
        servers = []
        
        if self.channel == "line":
            servers.append(self._create_line_mcp())
        
        # Future: Add more MCP servers
        # if self.channel in ("web", "telegram"):
        #     servers.append(self._create_calendar_mcp())
        
        return servers or None
    
    def _create_line_mcp(self) -> MCPServerStdio:
        """Create LINE MCP server."""
        return MCPServerStdio(
            name="line",
            command="npx",
            args=["@line/line-bot-mcp-server"],
            env={"CHANNEL_ACCESS_TOKEN": settings.LINE_CHANNEL_ACCESS_TOKEN},
        )
```

---

## Phase 3: Thread Persistence

Keep existing `SousChefThread` model but adapt for Agents SDK.

### 3.1 Thread Manager

```python
# services/thread_manager.py

class ThreadManager:
    """Manages conversation threads with Agents SDK."""
    
    def __init__(self, chef_id: int, family_id: int = None, channel: str = "web"):
        self.chef_id = chef_id
        self.family_id = family_id
        self.channel = channel
    
    def get_or_create_thread(self) -> SousChefThread:
        """Get active thread or create new one."""
        thread, created = SousChefThread.objects.get_or_create(
            chef_id=self.chef_id,
            family_id=self.family_id,
            family_type=self.family_type,
            channel=self.channel,  # NEW: track channel
            is_active=True,
            defaults={"family_name": self._get_family_name()}
        )
        return thread
    
    def save_turn(self, thread: SousChefThread, user_msg: str, assistant_msg: str):
        """Save a conversation turn."""
        SousChefMessage.objects.create(
            thread=thread, role="chef", content=user_msg
        )
        SousChefMessage.objects.create(
            thread=thread, role="assistant", content=assistant_msg
        )
    
    def get_history_for_agent(self, thread: SousChefThread) -> list:
        """Convert thread history to Agents SDK format."""
        messages = thread.messages.order_by('created_at')
        return [
            {"role": "user" if m.role == "chef" else "assistant", "content": m.content}
            for m in messages
        ]
```

---

## Phase 4: Unified Interface

### 4.1 Service Layer

```python
# services/sous_chef_service.py

class SousChefService:
    """
    Unified interface for Sous Chef - replaces SousChefAssistant.
    
    Usage:
        service = SousChefService(chef_id=1, channel="telegram")
        response = service.send_message("What orders do I have today?")
    """
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",
        family_id: int = None,
        family_type: str = None,
    ):
        self.factory = SousChefAgentFactory(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )
        self.thread_manager = ThreadManager(
            chef_id=chef_id,
            family_id=family_id,
            channel=channel,
        )
        self.agent = self.factory.create_agent()
    
    def send_message(self, message: str) -> dict:
        """Send message and get response (sync)."""
        thread = self.thread_manager.get_or_create_thread()
        
        # Get history for context
        history = self.thread_manager.get_history_for_agent(thread)
        
        # Run agent
        result = Runner.run_sync(
            self.agent,
            message,
            context={"history": history}  # If SDK supports
        )
        
        response = result.final_output
        
        # Save turn
        self.thread_manager.save_turn(thread, message, response)
        
        return {
            "status": "success",
            "message": response,
            "thread_id": thread.id,
        }
    
    async def send_message_async(self, message: str) -> dict:
        """Async version for better performance."""
        # Similar but with await Runner.run()
        pass
    
    def stream_message(self, message: str):
        """Stream response (for web UI)."""
        # Use Runner.run_streamed() when available
        pass
```

---

## Phase 5: Migration Path

### 5.1 Update Telegram Integration

```python
# chefs/tasks/telegram_tasks.py

def process_chef_message(chef, text: str) -> str:
    """Process via channel-aware Sous Chef."""
    from chefs.services.sous_chef_service import SousChefService
    
    service = SousChefService(
        chef_id=chef.id,
        channel="telegram",  # <- Channel awareness!
    )
    
    result = service.send_message(text)
    
    if result["status"] == "success":
        return result["message"]
    else:
        return "Sorry, something went wrong."
```

### 5.2 Update Web API

```python
# chefs/api/sous_chef.py

@api_view(['POST'])
def sous_chef_send_message(request):
    """Web dashboard endpoint."""
    service = SousChefService(
        chef_id=chef.id,
        channel="web",  # <- Full functionality
        family_id=request.data.get('family_id'),
        family_type=request.data.get('family_type'),
    )
    return Response(service.send_message(request.data['message']))
```

### 5.3 Deprecation

```python
# meals/sous_chef_assistant.py

import warnings

class SousChefAssistant:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "SousChefAssistant is deprecated. Use SousChefService instead.",
            DeprecationWarning
        )
        # Delegate to new service for backwards compat
        self._service = SousChefService(*args, **kwargs)
```

---

## Phase 6: Testing

### 6.1 Unit Tests

```python
# tests/test_sous_chef_service.py

def test_telegram_channel_excludes_navigation_tools():
    service = SousChefService(chef_id=1, channel="telegram")
    tool_names = [t.name for t in service.agent.tools]
    
    assert "get_upcoming_orders" in tool_names  # Core - included
    assert "navigate_to_tab" not in tool_names  # Navigation - excluded

def test_web_channel_includes_navigation_tools():
    service = SousChefService(chef_id=1, channel="web")
    tool_names = [t.name for t in service.agent.tools]
    
    assert "navigate_to_tab" in tool_names  # Navigation - included
```

---

## File Structure (Final)

```
chefs/
  services/
    sous_chef/
      __init__.py
      agent_factory.py      # SousChefAgentFactory
      service.py            # SousChefService (main interface)
      thread_manager.py     # Thread persistence
      tools/
        __init__.py
        categories.py       # Tool categories & registry
        loader.py           # Channel-aware tool loading
        core.py             # Core tools (all channels)
        navigation.py       # Web-only tools
        messaging.py        # Telegram/LINE tools
      prompts/
        base.py             # Base system prompt
        telegram.py         # Telegram additions
        line.py             # LINE additions
```

---

## Implementation Order

1. **Week 1: Foundation**
   - [ ] Create `chefs/services/sous_chef/` structure
   - [ ] Port tools to new categories system
   - [ ] Create `SousChefAgentFactory`

2. **Week 2: Core Service**
   - [ ] Implement `SousChefService`
   - [ ] Implement `ThreadManager` 
   - [ ] Add channel-aware prompts

3. **Week 3: Integration**
   - [ ] Update Telegram to use new service
   - [ ] Update web API to use new service
   - [ ] Add LINE MCP integration

4. **Week 4: Testing & Cleanup**
   - [ ] Comprehensive tests
   - [ ] Deprecate old `SousChefAssistant`
   - [ ] Documentation

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Agents SDK missing features | Fall back to direct API for missing features |
| Thread history format changes | Migration script + backwards compat |
| MCP server reliability | Graceful degradation if MCP fails |
| Breaking existing web UI | Feature flag for gradual rollout |

---

## Questions to Resolve

1. **Streaming**: Does Agents SDK support streaming well enough for web UI?
2. **History**: How to pass conversation history to Agents SDK? (context param?)
3. **Model selection**: Keep dynamic model selection or standardize?
4. **Structured output**: Keep Pydantic schemas for tables/actions?

---

## Next Steps

1. Review this plan
2. Decide on implementation timeline
3. Start with Phase 1 (tool categories)
