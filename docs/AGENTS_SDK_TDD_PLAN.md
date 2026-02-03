# Agents SDK Refactor - TDD Plan

## Goal

Replace manual Groq agent loop with OpenAI Agents SDK while keeping Groq as the LLM backend.

## Key Decisions

1. **LLM Backend**: Groq via LiteLLM integration (`model="litellm/groq/llama-3.3-70b-versatile"`)
2. **Keep existing**: Tool implementations, ThreadManager, channel-aware categories
3. **Replace**: Manual agent loop in `service.py` → `Runner.run_sync()` / `Runner.run()`
4. **Add**: MCP support for future LINE integration

## Dependencies

```bash
pip install "openai-agents[litellm]>=0.6.0"
```

---

## Phase 1: Agent Creation (TDD)

### Tests First

```python
# test_agents_sdk.py

class TestAgentCreation:
    """Test that we can create Agents SDK agents."""
    
    def test_create_basic_agent(self):
        """Can create an agent with instructions."""
        from agents import Agent
        
        agent = Agent(
            name="Test Agent",
            instructions="You are helpful.",
        )
        assert agent.name == "Test Agent"
    
    def test_create_agent_with_groq_model(self):
        """Can create agent with Groq via LiteLLM."""
        from agents import Agent
        
        agent = Agent(
            name="Groq Agent",
            instructions="You are helpful.",
            model="litellm/groq/llama-3.3-70b-versatile",
        )
        assert "groq" in agent.model
    
    def test_create_agent_with_function_tools(self):
        """Can create agent with function tools."""
        from agents import Agent, function_tool
        
        @function_tool
        def get_time() -> str:
            """Get current time."""
            return "12:00"
        
        agent = Agent(
            name="Tool Agent",
            instructions="You help with time.",
            tools=[get_time],
        )
        assert len(agent.tools) == 1
```

### Implementation

```python
# chefs/services/sous_chef/agents_factory.py

from agents import Agent, function_tool
from typing import List, Optional

class AgentsSousChefFactory:
    """Factory for creating Sous Chef agents using Agents SDK."""
    
    GROQ_MODEL = "litellm/groq/llama-3.3-70b-versatile"
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",
        family_id: Optional[int] = None,
        family_type: Optional[str] = None,
    ):
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
    
    def create_agent(self) -> Agent:
        """Create a configured Sous Chef agent."""
        return Agent(
            name=self._get_agent_name(),
            instructions=self._build_instructions(),
            model=self.GROQ_MODEL,
            tools=self._get_tools(),
            mcp_servers=self._get_mcp_servers(),
        )
```

---

## Phase 2: Tool Conversion (TDD)

### Tests First

```python
class TestToolConversion:
    """Test converting existing tools to Agents SDK format."""
    
    def test_function_tool_decorator(self):
        """@function_tool creates valid tool."""
        from agents import function_tool
        
        @function_tool
        def sample_tool(arg1: str, arg2: int = 5) -> dict:
            """A sample tool for testing."""
            return {"arg1": arg1, "arg2": arg2}
        
        # Should have proper schema
        assert sample_tool.name == "sample_tool"
        assert "arg1" in str(sample_tool)
    
    def test_convert_dietary_tool(self):
        """Can convert get_family_dietary_summary to function_tool."""
        from chefs.services.sous_chef.tools.agents_tools import get_family_dietary_summary
        
        # Should be callable and return expected structure
        result = get_family_dietary_summary(family_id=1, family_type="customer")
        assert "status" in result
    
    def test_tools_for_channel_are_decorated(self):
        """Channel tools should all be function_tool decorated."""
        from chefs.services.sous_chef.tools.agents_tools import get_tools_for_agents
        
        tools = get_tools_for_agents(channel="telegram")
        for tool in tools:
            # All tools should have function_tool attributes
            assert hasattr(tool, 'name')
```

### Implementation

```python
# chefs/services/sous_chef/tools/agents_tools.py

from agents import function_tool
from typing import Dict, Any, List, Optional

@function_tool  
def get_family_dietary_summary(
    family_id: int,
    family_type: str,
) -> Dict[str, Any]:
    """
    Get dietary preferences and restrictions for a family.
    
    Args:
        family_id: The family/customer ID
        family_type: Either 'customer' or 'lead'
    
    Returns:
        Dictionary with dietary restrictions, allergies, and member details.
    """
    # Call existing implementation
    from meals.sous_chef_tools import _get_family_dietary_summary
    # ... wrapper logic
```

---

## Phase 3: Runner Integration (TDD)

### Tests First

```python
class TestRunnerIntegration:
    """Test running agents with the Runner."""
    
    @pytest.mark.asyncio
    async def test_runner_basic(self):
        """Runner.run executes agent and returns result."""
        from agents import Agent, Runner
        
        agent = Agent(
            name="Echo",
            instructions="Echo the user's message back.",
            model="litellm/groq/llama-3.3-70b-versatile",
        )
        
        result = await Runner.run(agent, "Hello")
        assert result.final_output is not None
        assert len(result.final_output) > 0
    
    def test_runner_sync(self):
        """Runner.run_sync works for Django views."""
        from agents import Agent, Runner
        
        agent = Agent(
            name="Echo",
            instructions="Say 'OK'",
            model="litellm/groq/llama-3.3-70b-versatile",
        )
        
        result = Runner.run_sync(agent, "Test")
        assert result.final_output is not None
    
    @pytest.mark.asyncio
    async def test_runner_with_tools(self, mock_chef, mock_customer):
        """Runner executes tool calls correctly."""
        from chefs.services.sous_chef.agents_factory import AgentsSousChefFactory
        from agents import Runner
        
        factory = AgentsSousChefFactory(
            chef_id=mock_chef.id,
            channel="web",
        )
        agent = factory.create_agent()
        
        result = await Runner.run(agent, "What time is it?")
        # Should have executed tool and returned result
        assert result.final_output
```

---

## Phase 4: Service Layer (TDD)

### Tests First

```python
class TestAgentsSousChefService:
    """Test the new Agents SDK service layer."""
    
    @pytest.mark.django_db
    def test_service_send_message(self, test_chef):
        """Service.send_message returns response."""
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        result = service.send_message("Hello")
        
        assert result["status"] == "success"
        assert "message" in result
        assert "thread_id" in result
    
    @pytest.mark.django_db
    def test_service_saves_history(self, test_chef):
        """Service saves conversation to thread."""
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        from chefs.models import SousChefThread
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="web",
        )
        
        service.send_message("Hello")
        
        thread = SousChefThread.objects.filter(chef=test_chef).first()
        assert thread is not None
        assert thread.messages.count() >= 2  # user + assistant
    
    @pytest.mark.django_db
    def test_service_respects_channel(self, test_chef):
        """Telegram service excludes navigation tools."""
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        tool_names = [t.name for t in service.agent.tools]
        
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "get_upcoming_family_orders" in tool_names
```

### Implementation

```python
# chefs/services/sous_chef/agents_service.py

from agents import Agent, Runner
from .agents_factory import AgentsSousChefFactory
from .thread_manager import ThreadManager

class AgentsSousChefService:
    """
    Sous Chef service using OpenAI Agents SDK.
    
    Drop-in replacement for SousChefService with Agents SDK backend.
    """
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",
        family_id: int = None,
        family_type: str = None,
    ):
        self.factory = AgentsSousChefFactory(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )
        self.thread_manager = ThreadManager(
            chef_id=chef_id,
            family_id=family_id,
            family_type=family_type,
            channel=channel,
        )
        self.agent = self.factory.create_agent()
        self.channel = channel
    
    def send_message(self, message: str) -> dict:
        """Send message and get response (sync)."""
        thread = self.thread_manager.get_or_create_thread()
        
        # Run agent
        result = Runner.run_sync(self.agent, message)
        response = result.final_output
        
        # Save turn
        self.thread_manager.save_turn(message, response)
        
        return {
            "status": "success",
            "message": response,
            "thread_id": thread.id,
        }
```

---

## Phase 5: Migration & Feature Flag

### Tests First

```python
class TestMigration:
    """Test migration from old to new service."""
    
    def test_feature_flag_controls_backend(self, test_chef, settings):
        """USE_AGENTS_SDK flag switches implementation."""
        from chefs.services.sous_chef import get_sous_chef_service
        
        settings.USE_AGENTS_SDK = False
        old_service = get_sous_chef_service(chef_id=test_chef.id)
        assert old_service.__class__.__name__ == "SousChefService"
        
        settings.USE_AGENTS_SDK = True
        new_service = get_sous_chef_service(chef_id=test_chef.id)
        assert new_service.__class__.__name__ == "AgentsSousChefService"
    
    def test_both_services_same_interface(self, test_chef):
        """Both services have same public interface."""
        from chefs.services.sous_chef.service import SousChefService
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        old = SousChefService(chef_id=test_chef.id)
        new = AgentsSousChefService(chef_id=test_chef.id)
        
        # Same methods
        assert hasattr(old, 'send_message')
        assert hasattr(new, 'send_message')
        assert hasattr(old, 'stream_message')
        assert hasattr(new, 'stream_message')
```

---

## File Structure

```
chefs/services/sous_chef/
├── __init__.py              # Exports get_sous_chef_service()
├── service.py               # Existing Groq-based service
├── agents_service.py        # NEW: Agents SDK service
├── agents_factory.py        # NEW: Agents SDK factory
├── thread_manager.py        # Shared
├── tools/
│   ├── categories.py        # Shared
│   ├── loader.py            # Shared
│   └── agents_tools.py      # NEW: @function_tool decorated tools
└── tests/
    ├── test_agents_sdk.py   # NEW: Agents SDK tests
    └── ...
```

---

## Implementation Order

1. **Phase 1**: Create `agents_factory.py` with basic agent creation (TDD)
2. **Phase 2**: Create `agents_tools.py` with decorated tools (TDD)
3. **Phase 3**: Test Runner integration with real Groq calls
4. **Phase 4**: Create `agents_service.py` with full service (TDD)
5. **Phase 5**: Add feature flag and migration path

---

## Questions to Resolve

1. **History**: How to pass conversation history to Agents SDK?
   - Option A: Include in instructions dynamically
   - Option B: Use `context` parameter if supported
   
2. **Streaming**: Does `Runner.run_streamed()` exist?
   - Need to check SDK docs

3. **Error handling**: How does Agents SDK surface errors?

---

## Next Step

Start with Phase 1 tests - create `test_agents_sdk.py` with agent creation tests.
