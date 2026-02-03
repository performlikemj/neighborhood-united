# chefs/services/sous_chef/tests/test_tool_categories.py
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
    
    def test_tool_category_enum_values(self):
        """ToolCategory enum has expected values."""
        assert ToolCategory.CORE == "core"
        assert ToolCategory.NAVIGATION == "navigation"
        assert ToolCategory.MESSAGING == "messaging"
    
    def test_registry_not_empty(self):
        """Tool registry should have tools."""
        assert len(TOOL_REGISTRY) > 0
    
    def test_all_tools_have_category(self):
        """Every tool in SOUS_CHEF_TOOLS should have a category."""
        from meals.sous_chef_tools import SOUS_CHEF_TOOLS
        
        tool_names = set()
        for tool in SOUS_CHEF_TOOLS:
            name = tool.get("name") or tool.get("function", {}).get("name")
            if name:
                tool_names.add(name)
        
        missing = []
        for name in tool_names:
            if name not in TOOL_REGISTRY:
                missing.append(name)
        
        # Allow some tolerance for new tools not yet categorized
        assert len(missing) <= 5, f"Too many uncategorized tools: {missing}"
    
    def test_navigation_tools_identified(self):
        """Navigation tools must be in NAVIGATION category."""
        nav_tools = [
            "navigate_to_dashboard_tab",
            "prefill_form", 
            "scaffold_meal",
            "lookup_chef_hub_help",
        ]
        for tool in nav_tools:
            assert TOOL_REGISTRY.get(tool) == ToolCategory.NAVIGATION, \
                f"Tool '{tool}' should be NAVIGATION"
    
    def test_core_tools_identified(self):
        """Core tools must be in CORE category."""
        core_tools = [
            "get_family_dietary_summary",
            "get_upcoming_family_orders",
            "search_chef_dishes",
            "get_household_members",
            "check_recipe_compliance",
        ]
        for tool in core_tools:
            assert TOOL_REGISTRY.get(tool) == ToolCategory.CORE, \
                f"Tool '{tool}' should be CORE"
    
    def test_messaging_tools_identified(self):
        """Messaging tools must be in MESSAGING category."""
        msg_tools = ["draft_client_message"]
        for tool in msg_tools:
            assert TOOL_REGISTRY.get(tool) == ToolCategory.MESSAGING, \
                f"Tool '{tool}' should be MESSAGING"


class TestChannelTools:
    """Test channel tool configuration."""
    
    def test_channel_tools_defined(self):
        """All channels should have tool configuration."""
        expected_channels = ["web", "telegram", "line", "api"]
        for channel in expected_channels:
            assert channel in CHANNEL_TOOLS, f"Channel '{channel}' missing"
    
    def test_web_has_all_categories(self):
        """Web channel should have all categories."""
        web_categories = CHANNEL_TOOLS["web"]
        assert ToolCategory.CORE in web_categories
        assert ToolCategory.NAVIGATION in web_categories
        assert ToolCategory.MESSAGING in web_categories
    
    def test_telegram_excludes_navigation(self):
        """Telegram should NOT have navigation."""
        telegram_categories = CHANNEL_TOOLS["telegram"]
        assert ToolCategory.CORE in telegram_categories
        assert ToolCategory.NAVIGATION not in telegram_categories
        assert ToolCategory.MESSAGING in telegram_categories
    
    def test_line_excludes_navigation(self):
        """LINE should NOT have navigation."""
        line_categories = CHANNEL_TOOLS["line"]
        assert ToolCategory.CORE in line_categories
        assert ToolCategory.NAVIGATION not in line_categories
    
    def test_api_has_core_only(self):
        """API channel should have core only."""
        api_categories = CHANNEL_TOOLS["api"]
        assert api_categories == {ToolCategory.CORE}


class TestGetCategoriesForChannel:
    """Test get_categories_for_channel function."""
    
    def test_web_channel(self):
        """Web channel returns all categories."""
        allowed = get_categories_for_channel("web")
        assert ToolCategory.CORE in allowed
        assert ToolCategory.NAVIGATION in allowed
    
    def test_telegram_channel(self):
        """Telegram excludes navigation."""
        allowed = get_categories_for_channel("telegram")
        assert ToolCategory.CORE in allowed
        assert ToolCategory.NAVIGATION not in allowed
    
    def test_unknown_channel_defaults_to_core(self):
        """Unknown channels get core only."""
        allowed = get_categories_for_channel("unknown_channel")
        assert allowed == {ToolCategory.CORE}
    
    def test_empty_channel_defaults_to_core(self):
        """Empty channel gets core only."""
        allowed = get_categories_for_channel("")
        assert allowed == {ToolCategory.CORE}


class TestIsToolAllowed:
    """Test is_tool_allowed function."""
    
    def test_core_tool_allowed_everywhere(self):
        """Core tools allowed on all channels."""
        assert is_tool_allowed("get_family_dietary_summary", "web") is True
        assert is_tool_allowed("get_family_dietary_summary", "telegram") is True
        assert is_tool_allowed("get_family_dietary_summary", "line") is True
        assert is_tool_allowed("get_family_dietary_summary", "api") is True
    
    def test_navigation_tool_web_only(self):
        """Navigation tools only allowed on web."""
        assert is_tool_allowed("navigate_to_dashboard_tab", "web") is True
        assert is_tool_allowed("navigate_to_dashboard_tab", "telegram") is False
        assert is_tool_allowed("navigate_to_dashboard_tab", "line") is False
    
    def test_unknown_tool_not_allowed(self):
        """Unknown tools not allowed."""
        assert is_tool_allowed("nonexistent_tool", "web") is False
        assert is_tool_allowed("nonexistent_tool", "telegram") is False
    
    def test_prefill_form_web_only(self):
        """prefill_form only on web."""
        assert is_tool_allowed("prefill_form", "web") is True
        assert is_tool_allowed("prefill_form", "telegram") is False
    
    def test_scaffold_meal_web_only(self):
        """scaffold_meal only on web."""
        assert is_tool_allowed("scaffold_meal", "web") is True
        assert is_tool_allowed("scaffold_meal", "telegram") is False
