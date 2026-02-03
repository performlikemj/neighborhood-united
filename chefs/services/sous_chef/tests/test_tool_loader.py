# chefs/services/sous_chef/tests/test_tool_loader.py
"""Tests for channel-aware tool loading."""
import pytest


class TestGetToolSchemasForChannel:
    """Test loading tool schemas for channels."""
    
    def test_returns_list(self):
        """Should return a list."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        result = get_tool_schemas_for_channel("web")
        assert isinstance(result, list)
    
    def test_web_loads_tools(self):
        """Web channel should load tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        web_tools = get_tool_schemas_for_channel("web")
        assert len(web_tools) > 0
    
    def test_telegram_loads_tools(self):
        """Telegram channel should load tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        assert len(telegram_tools) > 0
    
    def test_telegram_has_fewer_tools_than_web(self):
        """Telegram should have fewer tools than web."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        web_tools = get_tool_schemas_for_channel("web")
        telegram_tools = get_tool_schemas_for_channel("telegram")
        
        assert len(telegram_tools) < len(web_tools), \
            f"Telegram ({len(telegram_tools)}) should have fewer tools than web ({len(web_tools)})"
    
    def test_telegram_excludes_navigate_tool(self):
        """Telegram should exclude navigate_to_dashboard_tab."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in telegram_tools
        ]
        
        assert "navigate_to_dashboard_tab" not in tool_names
    
    def test_telegram_excludes_prefill_form(self):
        """Telegram should exclude prefill_form."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in telegram_tools
        ]
        
        assert "prefill_form" not in tool_names
    
    def test_telegram_excludes_scaffold_meal(self):
        """Telegram should exclude scaffold_meal."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in telegram_tools
        ]
        
        assert "scaffold_meal" not in tool_names
    
    def test_telegram_includes_core_tools(self):
        """Telegram should include core tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        telegram_tools = get_tool_schemas_for_channel("telegram")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in telegram_tools
        ]
        
        # Core tools should be present
        assert "get_family_dietary_summary" in tool_names
        assert "search_chef_dishes" in tool_names
    
    def test_web_includes_navigation_tools(self):
        """Web should include navigation tools."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        web_tools = get_tool_schemas_for_channel("web")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in web_tools
        ]
        
        assert "navigate_to_dashboard_tab" in tool_names
        assert "prefill_form" in tool_names
    
    def test_tools_have_valid_schema(self):
        """All returned tools must have valid schema."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        for channel in ["web", "telegram", "line"]:
            tools = get_tool_schemas_for_channel(channel)
            
            for tool in tools:
                # Must have name (either directly or in function)
                name = tool.get("name") or tool.get("function", {}).get("name")
                assert name is not None, f"Tool missing name in {channel}"
                
                # Must have type or function key
                has_type = tool.get("type") == "function"
                has_function = "function" in tool
                assert has_type or has_function, f"Tool {name} missing type/function"
    
    def test_unknown_channel_returns_core_only(self):
        """Unknown channel should return core tools only."""
        from chefs.services.sous_chef.tools import get_tool_schemas_for_channel
        
        unknown_tools = get_tool_schemas_for_channel("unknown_channel")
        tool_names = [
            t.get("name") or t.get("function", {}).get("name")
            for t in unknown_tools
        ]
        
        # Should have core tools
        assert len(unknown_tools) > 0
        
        # Should not have navigation
        assert "navigate_to_dashboard_tab" not in tool_names


class TestGetToolsForChannel:
    """Test getting tool handlers."""
    
    def test_returns_dict(self):
        """Should return a dict."""
        from chefs.services.sous_chef.tools import get_tools_for_channel
        
        result = get_tools_for_channel("web")
        assert isinstance(result, dict)
    
    def test_web_has_handlers(self):
        """Web should have tool handlers."""
        from chefs.services.sous_chef.tools import get_tools_for_channel
        
        handlers = get_tools_for_channel("web")
        assert len(handlers) > 0
    
    def test_telegram_excludes_navigation_handlers(self):
        """Telegram handlers should exclude navigation."""
        from chefs.services.sous_chef.tools import get_tools_for_channel
        
        handlers = get_tools_for_channel("telegram")
        
        assert "navigate_to_dashboard_tab" not in handlers
        assert "prefill_form" not in handlers
