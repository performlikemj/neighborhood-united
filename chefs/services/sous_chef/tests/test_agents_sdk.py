# chefs/services/sous_chef/tests/test_agents_sdk.py
"""
TDD tests for OpenAI Agents SDK integration.

Phase 1: Agent Creation
Phase 2: Tool Conversion  
Phase 3: Runner Integration
Phase 4: Service Layer
Phase 5: Migration
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# =============================================================================
# Phase 1: Agent Creation
# =============================================================================

class TestAgentCreation:
    """Test that we can create Agents SDK agents."""
    
    def test_agents_sdk_importable(self):
        """Agents SDK package is installed and importable."""
        try:
            from agents import Agent, Runner, function_tool
            assert Agent is not None
            assert Runner is not None
            assert function_tool is not None
        except ImportError as e:
            pytest.skip(f"openai-agents not installed: {e}")
    
    def test_create_basic_agent(self):
        """Can create an agent with name and instructions."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        agent = Agent(
            name="Test Agent",
            instructions="You are a helpful assistant.",
        )
        
        assert agent.name == "Test Agent"
        assert "helpful" in agent.instructions
    
    def test_create_agent_with_model(self):
        """Can create agent with specific model."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        agent = Agent(
            name="Model Agent",
            instructions="You are helpful.",
            model="litellm/groq/llama-3.3-70b-versatile",
        )
        
        # Model should be set
        assert agent.model is not None
    
    def test_create_agent_with_function_tool(self):
        """Can create agent with @function_tool decorated functions."""
        try:
            from agents import Agent, function_tool
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        @function_tool
        def get_time() -> str:
            """Get the current time."""
            return "12:00 PM"
        
        agent = Agent(
            name="Tool Agent",
            instructions="You help with time.",
            tools=[get_time],
        )
        
        assert len(agent.tools) == 1


class TestAgentsSousChefFactory:
    """Test the Agents SDK factory for Sous Chef."""
    
    @pytest.mark.django_db
    def test_factory_creates_agent(self, test_chef):
        """Factory creates a valid Agent instance."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_factory import AgentsSousChefFactory
        
        factory = AgentsSousChefFactory(
            chef_id=test_chef.id,
            channel="web",
        )
        
        agent = factory.create_agent()
        
        assert isinstance(agent, Agent)
        assert "Sous Chef" in agent.name
    
    @pytest.mark.django_db
    def test_factory_uses_groq_model(self, test_chef):
        """Factory configures Groq via LiteLLM."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_factory import AgentsSousChefFactory
        
        factory = AgentsSousChefFactory(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        agent = factory.create_agent()
        
        # Should use Groq via LiteLLM
        assert "groq" in str(agent.model).lower() or "litellm" in str(agent.model).lower()
    
    @pytest.mark.django_db
    def test_factory_includes_channel_context(self, test_chef):
        """Factory includes channel-specific instructions."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_factory import AgentsSousChefFactory
        
        telegram_factory = AgentsSousChefFactory(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        agent = telegram_factory.create_agent()
        
        # Should mention Telegram limitations
        assert "telegram" in agent.instructions.lower() or "navigation" in agent.instructions.lower()
    
    @pytest.mark.django_db
    def test_factory_loads_channel_tools(self, test_chef):
        """Factory loads appropriate tools for channel."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_factory import AgentsSousChefFactory
        
        factory = AgentsSousChefFactory(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        agent = factory.create_agent()
        tool_names = [t.name for t in agent.tools] if agent.tools else []
        
        # Navigation tools should be excluded from Telegram
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "prefill_form" not in tool_names


# =============================================================================
# Phase 2: Tool Conversion
# =============================================================================

class TestToolConversion:
    """Test converting existing tools to @function_tool format."""
    
    def test_function_tool_decorator_works(self):
        """@function_tool decorator creates callable with metadata."""
        try:
            from agents import function_tool
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        @function_tool
        def sample_tool(arg1: str, arg2: int = 5) -> dict:
            """A sample tool that does something useful."""
            return {"arg1": arg1, "arg2": arg2}
        
        # Should be callable
        result = sample_tool("test", 10)
        assert result == {"arg1": "test", "arg2": 10}
        
        # Should have name attribute
        assert hasattr(sample_tool, 'name') or callable(sample_tool)
    
    def test_agents_tools_module_exists(self):
        """agents_tools.py module should exist and be importable."""
        try:
            from chefs.services.sous_chef.tools import agents_tools
            assert agents_tools is not None
        except ImportError as e:
            pytest.fail(f"agents_tools module not found: {e}")
    
    def test_get_tools_for_agents_returns_list(self):
        """get_tools_for_agents returns list of function tools."""
        try:
            from agents import function_tool
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.tools.agents_tools import get_tools_for_agents
        
        tools = get_tools_for_agents(channel="web")
        
        assert isinstance(tools, list)
        assert len(tools) > 0
    
    def test_telegram_tools_exclude_navigation(self):
        """Telegram channel tools don't include navigation."""
        try:
            from agents import function_tool
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.tools.agents_tools import get_tools_for_agents
        
        tools = get_tools_for_agents(channel="telegram")
        tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tools]
        
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "prefill_form" not in tool_names
        assert "scaffold_meal" not in tool_names


# =============================================================================
# Phase 3: Runner Integration  
# =============================================================================

class TestRunnerIntegration:
    """Test running agents with the Agents SDK Runner."""
    
    def test_runner_run_sync_exists(self):
        """Runner.run_sync method exists."""
        try:
            from agents import Runner
            assert hasattr(Runner, 'run_sync')
        except ImportError:
            pytest.skip("openai-agents not installed")
    
    @pytest.mark.skip(reason="Requires actual API call - run manually")
    def test_runner_basic_call(self):
        """Runner can execute a basic agent call."""
        try:
            from agents import Agent, Runner
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        agent = Agent(
            name="Echo",
            instructions="Reply with 'OK' to any message.",
            model="litellm/groq/llama-3.3-70b-versatile",
        )
        
        result = Runner.run_sync(agent, "Hello")
        
        assert result is not None
        assert result.final_output is not None
    
    @pytest.mark.skip(reason="Requires actual API call - run manually")  
    def test_runner_with_tool_call(self):
        """Runner executes tool calls and returns results."""
        try:
            from agents import Agent, Runner, function_tool
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        @function_tool
        def get_current_time() -> str:
            """Get the current time."""
            from datetime import datetime
            return datetime.now().strftime("%H:%M")
        
        agent = Agent(
            name="Time Agent",
            instructions="When asked for time, use the get_current_time tool.",
            model="litellm/groq/llama-3.3-70b-versatile",
            tools=[get_current_time],
        )
        
        result = Runner.run_sync(agent, "What time is it?")
        
        assert result.final_output is not None
        # Response should contain time-like content
        assert ":" in result.final_output or "time" in result.final_output.lower()


# =============================================================================
# Phase 4: Service Layer
# =============================================================================

class TestAgentsSousChefService:
    """Test the Agents SDK-based service layer."""
    
    @pytest.mark.django_db
    def test_service_instantiation(self, test_chef):
        """Service can be instantiated with chef_id."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        assert service.chef_id == test_chef.id
        assert service.channel == "telegram"
        assert service.agent is not None
    
    @pytest.mark.django_db
    def test_service_has_send_message(self, test_chef):
        """Service has send_message method."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="web",
        )
        
        assert hasattr(service, 'send_message')
        assert callable(service.send_message)
    
    @pytest.mark.django_db
    @patch('agents.Runner.run_sync')
    def test_service_send_message_returns_response(self, mock_runner, test_chef):
        """send_message returns dict with status, message, thread_id."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        # Mock the runner response
        mock_result = MagicMock()
        mock_result.final_output = "Hello! I'm your Sous Chef."
        mock_runner.return_value = mock_result
        
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
    @patch('agents.Runner.run_sync')
    def test_service_saves_to_thread(self, mock_runner, test_chef):
        """Service saves messages to thread."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        mock_result = MagicMock()
        mock_result.final_output = "Hello!"
        mock_runner.return_value = mock_result
        
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        from chefs.models import SousChefThread
        
        service = AgentsSousChefService(
            chef_id=test_chef.id,
            channel="web",
        )
        
        service.send_message("Hi there")
        
        # Should have created a thread
        thread = SousChefThread.objects.filter(chef=test_chef).first()
        assert thread is not None


# =============================================================================
# Phase 5: Migration & Feature Flag
# =============================================================================

class TestMigration:
    """Test migration path from old to new service."""
    
    @pytest.mark.django_db
    def test_both_services_have_same_interface(self, test_chef):
        """Old and new services have compatible interfaces."""
        try:
            from agents import Agent
        except ImportError:
            pytest.skip("openai-agents not installed")
        
        from chefs.services.sous_chef.service import SousChefService
        from chefs.services.sous_chef.agents_service import AgentsSousChefService
        
        old_service = SousChefService(chef_id=test_chef.id)
        new_service = AgentsSousChefService(chef_id=test_chef.id)
        
        # Both should have send_message
        assert hasattr(old_service, 'send_message')
        assert hasattr(new_service, 'send_message')
        
        # Both should have channel attribute
        assert hasattr(old_service, 'channel')
        assert hasattr(new_service, 'channel')
    
    @pytest.mark.django_db
    def test_get_service_function_exists(self, test_chef):
        """get_sous_chef_service factory function exists."""
        from chefs.services.sous_chef import get_sous_chef_service
        
        service = get_sous_chef_service(
            chef_id=test_chef.id,
            channel="telegram",
        )
        
        assert service is not None
        assert hasattr(service, 'send_message')
