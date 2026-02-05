# chefs/services/sous_chef/tests/test_prompt_builder.py
"""Tests for channel-aware prompt building."""
import pytest


class TestGetChannelContext:
    """Test channel-specific context generation."""
    
    def test_returns_string(self):
        """Should return a string."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        result = get_channel_context("telegram")
        assert isinstance(result, str)
    
    def test_telegram_context_not_empty(self):
        """Telegram context should not be empty."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        assert len(context) > 0
    
    def test_telegram_context_mentions_constraints(self):
        """Telegram context must mention navigation constraints."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        context_lower = context.lower()
        
        # Should mention inability to navigate
        assert "cannot" in context_lower or "can't" in context_lower or "unable" in context_lower
        assert "navigate" in context_lower or "dashboard" in context_lower
    
    def test_telegram_context_mentions_security(self):
        """Telegram context must warn about sensitive data."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        context_lower = context.lower()
        
        # Should mention security/privacy concerns
        has_security = any(word in context_lower for word in [
            "health", "sensitive", "never", "security", "allerg", "dietary"
        ])
        assert has_security, "Telegram context should mention sensitive data handling"
    
    def test_telegram_context_identifies_channel(self):
        """Telegram context should identify it's Telegram."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("telegram")
        
        assert "telegram" in context.lower()
    
    def test_web_context_mentions_capabilities(self):
        """Web context should mention full capabilities."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("web")
        context_lower = context.lower()
        
        # Should mention navigation capabilities
        assert "navigate" in context_lower or "navigation" in context_lower
    
    def test_line_context_mentions_constraints(self):
        """LINE context should mention constraints."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("line")
        context_lower = context.lower()
        
        assert "line" in context_lower
    
    def test_unknown_channel_returns_web_default(self):
        """Unknown channel should return web context."""
        from chefs.services.sous_chef.prompts import get_channel_context
        
        context = get_channel_context("unknown")
        web_context = get_channel_context("web")
        
        # Should default to web
        assert context == web_context


class TestBuildSystemPrompt:
    """Test full system prompt building."""
    
    def test_returns_string(self):
        """Should return a string."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        result = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test family",
            tools_description="Test tools",
            channel="web",
        )
        
        assert isinstance(result, str)
    
    def test_prompt_not_empty(self):
        """Prompt should not be empty."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        result = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test",
            tools_description="Test",
            channel="web",
        )
        
        assert len(result) > 100
    
    def test_prompt_includes_chef_name(self):
        """Prompt must include the chef's name."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        prompt = build_system_prompt(
            chef_name="Chef Mario",
            family_context="Test family",
            tools_description="Test tools",
            channel="web",
        )
        
        assert "Chef Mario" in prompt or "Mario" in prompt
    
    def test_prompt_includes_family_context(self):
        """Prompt must include family context."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        family_ctx = "The Johnson family has a severe peanut allergy"
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context=family_ctx,
            tools_description="Test tools",
            channel="web",
        )
        
        assert family_ctx in prompt
    
    def test_prompt_includes_tools_description(self):
        """Prompt must include tools description."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        tools_desc = "• get_orders: Get upcoming orders"
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test",
            tools_description=tools_desc,
            channel="web",
        )
        
        assert "get_orders" in prompt
    
    def test_prompt_includes_channel_context_for_telegram(self):
        """Telegram prompt should include Telegram-specific context."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test",
            tools_description="Test",
            channel="telegram",
        )
        
        # Should mention Telegram constraints
        prompt_lower = prompt.lower()
        assert "telegram" in prompt_lower
        assert "cannot" in prompt_lower or "can't" in prompt_lower
    
    def test_prompt_structure_has_sections(self):
        """Prompt should have expected sections."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        prompt = build_system_prompt(
            chef_name="Chef Test",
            family_context="Test",
            tools_description="Test",
            channel="web",
        )
        
        prompt_lower = prompt.lower()
        
        # Should have key sections
        assert "identity" in prompt_lower or "role" in prompt_lower
        assert "mission" in prompt_lower or "help" in prompt_lower
        assert "tool" in prompt_lower or "capabilities" in prompt_lower
    
    def test_different_channels_produce_different_prompts(self):
        """Different channels should produce different prompts."""
        from chefs.services.sous_chef.prompts import build_system_prompt
        
        web_prompt = build_system_prompt(
            chef_name="Chef",
            family_context="Test",
            tools_description="Test",
            channel="web",
        )
        
        telegram_prompt = build_system_prompt(
            chef_name="Chef",
            family_context="Test",
            tools_description="Test",
            channel="telegram",
        )
        
        assert web_prompt != telegram_prompt
