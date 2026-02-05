# Sous Chef Agent Refactor - TDD Plan

## Overview

Refactor Sous Chef to use OpenAI Agents SDK (v0.6.x) with Groq backend.
Test-Driven Development approach: write tests first, then implement.

**SDK Versions (Feb 2026):**
- `openai-agents>=0.6.0` - Agent framework
- `openai>=2.16.0` - OpenAI client (for Agents SDK)
- `groq==0.31.1` - Keep existing (for backward compat)

**Key Agents SDK Features:**
- `Agent` - LLM with instructions, tools, guardrails
- `Runner` - Manages agent loop (sync/async)
- `function_tool` - Decorator for Python tools
- `Sessions` - Conversation history management
- `Guardrails` - Input/output validation
- Provider-agnostic - Supports Groq via model config

---

## Package Updates Required

```txt
# requirements.txt additions
openai-agents>=0.6.0
openai>=2.16.0
```

---

## Test Structure

```
chefs/services/sous_chef/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_tool_categories.py  # Tool filtering tests
│   ├── test_tool_loader.py      # Channel-aware loading
│   ├── test_prompt_builder.py   # System prompt tests
│   ├── test_thread_manager.py   # Conversation persistence
│   ├── test_agent_factory.py    # Agent creation
│   ├── test_service.py          # Main service tests
│   ├── test_telegram_integration.py  # End-to-end Telegram
│   └── test_guardrails.py       # Safety guardrails
```

---

## Phase 1: Tool Categories (Tests First)

### Test File: `test_tool_categories.py`

```python
"""Tests for tool category system."""
import pytest
from chefs.services.sous_chef.tools.categories import (
    ToolCategory,
    TOOL_REGISTRY,
    CHANNEL_TOOLS,
    get_categories_for_channel,
    is_tool_allowed,
)


class TestToolCategories:
    """Test tool category definitions."""
    
    def test_all_tools_have_category(self):
        """Every registered tool must have a category."""
        from meals.sous_chef_tools import SOUS_CHEF_TOOLS
        
        tool_names = {
            t.get("name") or t.get("function", {}).get("name")
            for t in SOUS_CHEF_TOOLS
        }
        
        for name in tool_names:
            if name:
                assert name in TOOL_REGISTRY, f"Tool '{name}' missing from registry"
    
    def test_navigation_tools_identified(self):
        """Navigation tools must be in NAVIGATION category."""
        nav_tools = [
            "navigate_to_dashboard_tab",
            "prefill_form", 
            "scaffold_meal",
            "lookup_chef_hub_help",
        ]
        for tool in nav_tools:
            assert TOOL_REGISTRY.get(tool) == ToolCategory.NAVIGATION
    
    def test_core_tools_identified(self):
        """Core tools must be in CORE category."""
        core_tools = [
            "get_family_dietary_summary",
            "get_upcoming_family_orders",
            "search_chef_dishes",
        ]
        for tool in core_tools:
            assert TOOL_REGISTRY.get(tool) == ToolCategory.CORE


class TestChannelFiltering:
    """Test channel-based tool filtering."""
    
    def test_web_channel_has_all_categories(self):
        """Web channel should have access to all tool categories."""
        allowed = get_categories_for_channel("web")
        assert ToolCategory.CORE in allowed
        assert ToolCategory.NAVIGATION in allowed
        assert ToolCategory.MESSAGING in allowed
    
    def test_telegram_channel_excludes_navigation(self):
        """Telegram should NOT have navigation tools."""
        allowed = get_categories_for_channel("telegram")
        assert ToolCategory.CORE in allowed
        assert ToolCategory.NAVIGATION not in allowed
        assert ToolCategory.MESSAGING in allowed
    
    def test_is_tool_allowed_web(self):
        """Web allows all tools."""
        assert is_tool_allowed("navigate_to_dashboard_tab", "web") is True
        assert is_tool_allowed("get_family_dietary_summary", "web") is True
    
    def test_is_tool_allowed_telegram(self):
        """Telegram excludes navigation."""
        assert is_tool_allowed("navigate_to_dashboard_tab", "telegram") is False
        assert is_tool_allowed("get_family_dietary_summary", "telegram") is True
    
    def test_unknown_channel_defaults_to_core_only(self):
        """Unknown channels get core tools only."""
        allowed = get_categories_for_channel("unknown_channel")
        assert allowed == {ToolCategory.CORE}
```

---

## Phase 2: Tool Loader (Tests First)

### Test File: `test_tool_loader.py`

```python
"""Tests for channel-aware tool loading."""
import pytest
from unittest.mock import patch, MagicMock


class TestToolSchemaLoading:
    """Test loading tool schemas for channels."""
    
    def test_web_loads_all_tools(self):
        """Web channel loads all available tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        from meals.sous_chef_tools import SOUS_CHEF_TOOLS
        
        web_tools = get_tool_schemas_for_channel("web")
        
        # Web should have all or nearly all tools
        assert len(web_tools) >= len(SOUS_CHEF_TOOLS) - 5  # Allow some margin
    
    def test_telegram_excludes_navigation_tools(self):
        """Telegram excludes navigation tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in telegram_tools
        ]
        
        # Navigation tools should be excluded
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "prefill_form" not in tool_names
        assert "scaffold_meal" not in tool_names
        
        # Core tools should be included
        assert "get_family_dietary_summary" in tool_names
        assert "search_chef_dishes" in tool_names
    
    def test_telegram_has_fewer_tools_than_web(self):
        """Telegram should have fewer tools than web."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        web_tools = get_tool_schemas_for_channel("web")
        telegram_tools = get_tool_schemas_for_channel("telegram")
        
        assert len(telegram_tools) < len(web_tools)
    
    def test_tools_have_valid_schema(self):
        """All returned tools must have valid schema."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        for channel in ["web", "telegram", "line"]:
            tools = get_tool_schemas_for_channel(channel)
            
            for tool in tools:
                # Must have name
                name = tool.get("name") or tool.get("function", {}).get("name")
                assert name is not None, f"Tool missing name in {channel}"
                
                # Must have type
                assert tool.get("type") == "function" or "function" in tool
```

---

## Phase 3: Prompt Builder (Tests First)

### Test File: `test_prompt_builder.py`

```python
"""Tests for channel-aware prompt building."""
import pytest


class TestChannelContext:
    """Test channel-specific context generation."""
    
    def test_telegram_context_includes_constraints(self):
        """Telegram context must mention navigation is unavailable."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        
        assert "CANNOT navigate" in context or "cannot navigate" in context.lower()
        assert "Telegram" in context
    
    def test_telegram_context_mentions_security(self):
        """Telegram context must warn about sensitive data."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        
        assert "health data" in context.lower() or "sensitive" in context.lower()
    
    def test_web_context_includes_full_capabilities(self):
        """Web context should mention navigation is available."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("web")
        
        assert "navigate" in context.lower()
        assert "prefill" in context.lower() or "form" in context.lower()


class TestPromptBuilder:
    """Test full system prompt building."""
    
    def test_prompt_includes_chef_name(self):
        """Prompt must include the chef's name."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        prompt = build_system_prompt(
            chef_name="Chef Mario",
            family_context="Test family",
            tools_description="Test tools",
            channel="web",
        )
        
        assert "Chef Mario" in prompt
    
    def test_prompt_includes_family_context(self):
        """Prompt must include family context."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        family_ctx = "Family has peanut allergy"
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context=family_ctx,
            tools_description="Test tools",
            channel="web",
        )
        
        assert family_ctx in prompt
    
    def test_prompt_includes_channel_context(self):
        """Prompt must include channel-specific context."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test",
            tools_description="Test",
            channel="telegram",
        )
        
        assert "Telegram" in prompt or "telegram" in prompt
```

---

## Phase 4: Thread Manager (Tests First)

### Test File: `test_thread_manager.py`

```python
"""Tests for conversation thread management."""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestThreadManager(TestCase):
    """Test conversation persistence."""
    
    @pytest.fixture(autouse=True)
    def setup_chef(self, db):
        """Create test chef."""
        from django.contrib.auth import get_user_model
        from chefs.models import Chef
        
        User = get_user_model()
        user = User.objects.create_user(
            username="testchef",
            email="test@example.com",
            password="testpass123"
        )
        self.chef = Chef.objects.create(user=user)
    
    def test_creates_new_thread_when_none_exists(self):
        """Should create thread if none exists."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=self.chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        assert thread is not None
        assert thread.chef_id == self.chef.id
        assert thread.is_active is True
    
    def test_returns_existing_active_thread(self):
        """Should return existing active thread."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=self.chef.id, channel="telegram")
        thread1 = manager.get_or_create_thread()
        thread2 = manager.get_or_create_thread()
        
        assert thread1.id == thread2.id
    
    def test_save_turn_creates_messages(self):
        """save_turn should create chef and assistant messages."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefMessage
        
        manager = ThreadManager(chef_id=self.chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        manager.save_turn("Hello", "Hi there!")
        
        messages = SousChefMessage.objects.filter(thread=thread)
        assert messages.count() == 2
        assert messages.filter(role="chef", content="Hello").exists()
        assert messages.filter(role="assistant", content="Hi there!").exists()
    
    def test_get_history_returns_messages(self):
        """get_history should return conversation messages."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=self.chef.id, channel="telegram")
        manager.save_turn("First message", "First response")
        manager.save_turn("Second message", "Second response")
        
        history = manager.get_history()
        
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "First message"
    
    def test_new_conversation_deactivates_old(self):
        """new_conversation should deactivate existing thread."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefThread
        
        manager = ThreadManager(chef_id=self.chef.id, channel="telegram")
        old_thread = manager.get_or_create_thread()
        old_id = old_thread.id
        
        new_thread = manager.new_conversation()
        
        assert new_thread.id != old_id
        old_thread.refresh_from_db()
        assert old_thread.is_active is False
```

---

## Phase 5: Agent Factory (Tests First)

### Test File: `test_agent_factory.py`

```python
"""Tests for agent factory."""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestAgentFactory(TestCase):
    """Test agent creation with channel configuration."""
    
    @pytest.fixture(autouse=True)
    def setup_chef(self, db):
        """Create test chef."""
        from django.contrib.auth import get_user_model
        from chefs.models import Chef
        
        User = get_user_model()
        user = User.objects.create_user(
            username="testchef",
            first_name="Mario",
            email="test@example.com",
            password="testpass123"
        )
        self.chef = Chef.objects.create(user=user)
    
    def test_factory_loads_chef(self):
        """Factory should load chef from database."""
        from chefs.services.sous_chef.agent_factory import SousChefAgentFactory
        
        factory = SousChefAgentFactory(chef_id=self.chef.id, channel="web")
        
        assert factory.chef.id == self.chef.id
    
    def test_factory_gets_chef_name(self):
        """Factory should extract chef display name."""
        from chefs.services.sous_chef.agent_factory import SousChefAgentFactory
        
        factory = SousChefAgentFactory(chef_id=self.chef.id, channel="web")
        
        assert factory.chef_name == "Mario"
    
    def test_factory_builds_system_prompt(self):
        """Factory should build valid system prompt."""
        from chefs.services.sous_chef.agent_factory import SousChefAgentFactory
        
        factory = SousChefAgentFactory(chef_id=self.chef.id, channel="telegram")
        prompt = factory.build_system_prompt()
        
        assert "Mario" in prompt
        assert "Telegram" in prompt or "telegram" in prompt.lower()
    
    def test_factory_gets_tools_for_channel(self):
        """Factory should return channel-appropriate tools."""
        from chefs.services.sous_chef.agent_factory import SousChefAgentFactory
        
        web_factory = SousChefAgentFactory(chef_id=self.chef.id, channel="web")
        telegram_factory = SousChefAgentFactory(chef_id=self.chef.id, channel="telegram")
        
        web_tools = web_factory.get_tools()
        telegram_tools = telegram_factory.get_tools()
        
        # Web has more tools
        assert len(web_tools) > len(telegram_tools)
        
        # Telegram missing navigation
        telegram_names = [t.get("name") for t in telegram_tools]
        assert "navigate_to_dashboard_tab" not in telegram_names
```

---

## Phase 6: Main Service (Tests First)

### Test File: `test_service.py`

```python
"""Tests for SousChefService."""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock, AsyncMock


class TestSousChefService(TestCase):
    """Test main service interface."""
    
    @pytest.fixture(autouse=True)
    def setup_chef(self, db):
        """Create test chef."""
        from django.contrib.auth import get_user_model
        from chefs.models import Chef
        
        User = get_user_model()
        user = User.objects.create_user(
            username="testchef",
            first_name="Mario",
            email="test@example.com",
            password="testpass123"
        )
        self.chef = Chef.objects.create(user=user)
    
    def test_service_initializes(self):
        """Service should initialize with chef and channel."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=self.chef.id, channel="telegram")
        
        assert service.chef_id == self.chef.id
        assert service.channel == "telegram"
    
    @patch("chefs.services.sous_chef.service.Groq")
    def test_send_message_returns_response(self, mock_groq_class):
        """send_message should return a response dict."""
        from chefs.services.sous_chef import SousChefService
        
        # Mock Groq response
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, Chef!"
        mock_response.choices[0].message.tool_calls = None
        mock_groq.chat.completions.create.return_value = mock_response
        
        service = SousChefService(chef_id=self.chef.id, channel="telegram")
        result = service.send_message("Hi there")
        
        assert result["status"] == "success"
        assert "message" in result
        assert result["message"] == "Hello, Chef!"
    
    @patch("chefs.services.sous_chef.service.Groq")
    def test_send_message_saves_to_thread(self, mock_groq_class):
        """send_message should persist conversation."""
        from chefs.services.sous_chef import SousChefService
        from customer_dashboard.models import SousChefMessage
        
        # Mock Groq
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_groq.chat.completions.create.return_value = mock_response
        
        service = SousChefService(chef_id=self.chef.id, channel="telegram")
        service.send_message("Test message")
        
        # Check messages were saved
        messages = SousChefMessage.objects.filter(
            thread__chef_id=self.chef.id
        )
        assert messages.count() >= 2
    
    @patch("chefs.services.sous_chef.service.Groq")
    def test_error_handling(self, mock_groq_class):
        """Service should handle errors gracefully."""
        from chefs.services.sous_chef import SousChefService
        
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_groq.chat.completions.create.side_effect = Exception("API Error")
        
        service = SousChefService(chef_id=self.chef.id, channel="telegram")
        result = service.send_message("Test")
        
        assert result["status"] == "error"
        assert "message" in result
```

---

## Phase 7: Telegram Integration (Tests First)

### Test File: `test_telegram_integration.py`

```python
"""End-to-end tests for Telegram integration."""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestTelegramMessageProcessing(TestCase):
    """Test Telegram message flow."""
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Create test chef with Telegram link."""
        from django.contrib.auth import get_user_model
        from chefs.models import Chef
        from chefs.models.telegram_integration import ChefTelegramLink
        
        User = get_user_model()
        user = User.objects.create_user(
            username="testchef",
            first_name="Mario",
            email="test@example.com"
        )
        self.chef = Chef.objects.create(user=user)
        self.telegram_link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=12345,
            telegram_username="testchef",
            is_active=True
        )
    
    @patch("chefs.services.sous_chef.service.Groq")
    def test_process_chef_message_uses_telegram_channel(self, mock_groq_class):
        """process_chef_message should use telegram channel."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        # Mock Groq
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_groq.chat.completions.create.return_value = mock_response
        
        result = process_chef_message(self.chef, "Hi")
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @patch("chefs.services.sous_chef.service.Groq")
    @patch("chefs.tasks.telegram_tasks.send_telegram_message")
    def test_full_webhook_flow(self, mock_send, mock_groq_class):
        """Test complete webhook → response flow."""
        from chefs.tasks.telegram_tasks import process_telegram_update
        
        # Mock Groq
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Got it!"
        mock_response.choices[0].message.tool_calls = None
        mock_groq.chat.completions.create.return_value = mock_response
        
        mock_send.return_value = True
        
        # Simulate webhook update
        update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "from": {"id": 12345, "first_name": "Test"},
                "chat": {"id": 12345},
                "text": "What orders do I have?"
            }
        }
        
        process_telegram_update(update)
        
        # Should have called send_telegram_message
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == 12345  # chat_id
        assert "Got it!" in call_args[0][1]  # response text


class TestTelegramToolFiltering(TestCase):
    """Test that Telegram excludes navigation tools."""
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Create test chef."""
        from django.contrib.auth import get_user_model
        from chefs.models import Chef
        
        User = get_user_model()
        user = User.objects.create_user(username="testchef", email="t@t.com")
        self.chef = Chef.objects.create(user=user)
    
    @patch("chefs.services.sous_chef.service.Groq")
    def test_navigation_tool_not_called(self, mock_groq_class):
        """Navigation tools should not be available for Telegram."""
        from chefs.services.sous_chef import SousChefService
        
        mock_groq = MagicMock()
        mock_groq_class.return_value = mock_groq
        
        service = SousChefService(chef_id=self.chef.id, channel="telegram")
        tools = service.factory.get_tools()
        
        tool_names = [t.get("name") for t in tools]
        
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "prefill_form" not in tool_names
        assert "scaffold_meal" not in tool_names
```

---

## Phase 8: Guardrails (Tests First)

### Test File: `test_guardrails.py`

```python
"""Tests for safety guardrails."""
import pytest


class TestSensitiveDataGuardrail:
    """Test sensitive data filtering."""
    
    def test_filters_allergy_info_for_telegram(self):
        """Should flag/filter allergy info in Telegram responses."""
        from chefs.services.sous_chef.guardrails import SensitiveDataGuardrail
        
        guardrail = SensitiveDataGuardrail(channel="telegram")
        
        response = "The customer has a severe peanut allergy."
        result = guardrail.check_output(response)
        
        # Should either block or sanitize
        assert result.action in ["block", "sanitize"]
    
    def test_allows_allergy_info_for_web(self):
        """Should allow allergy info in web responses."""
        from chefs.services.sous_chef.guardrails import SensitiveDataGuardrail
        
        guardrail = SensitiveDataGuardrail(channel="web")
        
        response = "The customer has a severe peanut allergy."
        result = guardrail.check_output(response)
        
        assert result.action == "allow"
    
    def test_allows_general_food_discussion(self):
        """Should allow general food discussion on any channel."""
        from chefs.services.sous_chef.guardrails import SensitiveDataGuardrail
        
        guardrail = SensitiveDataGuardrail(channel="telegram")
        
        response = "I recommend serving the salmon with a lemon dill sauce."
        result = guardrail.check_output(response)
        
        assert result.action == "allow"
```

---

## Implementation Order

### Step 1: Update Dependencies
```bash
pip install openai-agents>=0.6.0 openai>=2.16.0
# Add to requirements.txt
```

### Step 2: Run Initial Tests (They Will Fail)
```bash
pytest chefs/services/sous_chef/tests/ -v
```

### Step 3: Implement Each Module Until Tests Pass

1. **Tool Categories** → Run `test_tool_categories.py` → Implement → Pass
2. **Tool Loader** → Run `test_tool_loader.py` → Implement → Pass  
3. **Prompt Builder** → Run `test_prompt_builder.py` → Implement → Pass
4. **Thread Manager** → Run `test_thread_manager.py` → Implement → Pass
5. **Agent Factory** → Run `test_agent_factory.py` → Implement → Pass
6. **Service** → Run `test_service.py` → Implement → Pass
7. **Telegram Integration** → Run `test_telegram_integration.py` → Implement → Pass
8. **Guardrails** → Run `test_guardrails.py` → Implement → Pass

### Step 4: Integration Test
```bash
# Full test suite
pytest chefs/services/sous_chef/tests/ -v --tb=short

# Telegram specific
pytest chefs/tests/test_telegram*.py -v
```

### Step 5: Manual Verification
1. Deploy to staging
2. Send test message via Telegram
3. Verify response excludes navigation suggestions
4. Verify conversation persists

---

## Success Criteria

- [ ] All unit tests pass
- [ ] Telegram messages processed without navigation tools
- [ ] Responses sent back to Telegram
- [ ] Conversation history persisted
- [ ] No sensitive data leaked in Telegram responses
- [ ] Web API still works with full tools
- [ ] Streaming works for web UI

---

## Commands Reference

```bash
# Run all sous chef tests
pytest chefs/services/sous_chef/tests/ -v

# Run specific test file
pytest chefs/services/sous_chef/tests/test_service.py -v

# Run with coverage
pytest chefs/services/sous_chef/tests/ --cov=chefs.services.sous_chef --cov-report=term-missing

# Run Telegram integration tests
pytest chefs/tests/test_telegram*.py -v

# Quick smoke test
python -c "from chefs.services.sous_chef import SousChefService; print('Import OK')"
```
