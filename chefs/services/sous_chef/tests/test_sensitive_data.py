# chefs/services/sous_chef/tests/test_sensitive_data.py
"""
Tests for sensitive data handling in channel-aware Sous Chef.

TDD approach: These tests define the expected behavior before implementation.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestSensitiveCategories:
    """Phase 1: Test that sensitive tool category exists and is configured."""
    
    def test_sensitive_category_exists(self):
        """SENSITIVE should be a valid tool category."""
        from chefs.services.sous_chef.tools.categories import ToolCategory
        
        assert hasattr(ToolCategory, 'SENSITIVE')
        assert ToolCategory.SENSITIVE == "sensitive"
    
    def test_dietary_summary_is_sensitive(self):
        """get_family_dietary_summary should be marked as sensitive."""
        from chefs.services.sous_chef.tools.categories import (
            TOOL_REGISTRY, ToolCategory
        )
        
        assert "get_family_dietary_summary" in TOOL_REGISTRY
        assert TOOL_REGISTRY["get_family_dietary_summary"] == ToolCategory.SENSITIVE
    
    def test_household_members_is_sensitive(self):
        """get_household_members should be marked as sensitive."""
        from chefs.services.sous_chef.tools.categories import (
            TOOL_REGISTRY, ToolCategory
        )
        
        assert "get_household_members" in TOOL_REGISTRY
        assert TOOL_REGISTRY["get_household_members"] == ToolCategory.SENSITIVE
    
    def test_recipe_compliance_is_sensitive(self):
        """check_recipe_compliance should be marked as sensitive."""
        from chefs.services.sous_chef.tools.categories import (
            TOOL_REGISTRY, ToolCategory
        )
        
        assert "check_recipe_compliance" in TOOL_REGISTRY
        assert TOOL_REGISTRY["check_recipe_compliance"] == ToolCategory.SENSITIVE
    
    def test_order_history_is_not_sensitive(self):
        """get_family_order_history should NOT be sensitive (no health data)."""
        from chefs.services.sous_chef.tools.categories import (
            TOOL_REGISTRY, ToolCategory
        )
        
        assert "get_family_order_history" in TOOL_REGISTRY
        assert TOOL_REGISTRY["get_family_order_history"] == ToolCategory.CORE
    
    def test_telegram_includes_sensitive_category(self):
        """Telegram channel should include SENSITIVE (tools are loaded but wrapped)."""
        from chefs.services.sous_chef.tools.categories import (
            CHANNEL_TOOLS, ToolCategory
        )
        
        assert ToolCategory.SENSITIVE in CHANNEL_TOOLS["telegram"]
    
    def test_web_includes_sensitive_category(self):
        """Web channel should include SENSITIVE category."""
        from chefs.services.sous_chef.tools.categories import (
            CHANNEL_TOOLS, ToolCategory
        )
        
        assert ToolCategory.SENSITIVE in CHANNEL_TOOLS["web"]
    
    def test_sensitive_restricted_channels_defined(self):
        """Should define which channels restrict sensitive data."""
        from chefs.services.sous_chef.tools.categories import (
            SENSITIVE_RESTRICTED_CHANNELS
        )
        
        assert "telegram" in SENSITIVE_RESTRICTED_CHANNELS
        assert "line" in SENSITIVE_RESTRICTED_CHANNELS
        assert "web" not in SENSITIVE_RESTRICTED_CHANNELS


class TestSensitiveWrapper:
    """Phase 2: Test the sensitive data wrapper behavior."""
    
    def test_wrapper_blocks_dietary_on_telegram(self):
        """Dietary summary should be blocked on Telegram."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        # Mock the original tool function
        original_fn = MagicMock(return_value={"status": "success", "data": "sensitive"})
        
        wrapped = wrap_sensitive_tool(
            original_fn, 
            "get_family_dietary_summary", 
            channel="telegram"
        )
        result = wrapped({}, None, None, None)
        
        assert result["status"] == "restricted"
        assert "telegram" in result["channel"]
        assert "dashboard" in result["message"].lower()
        # Original function should NOT be called
        original_fn.assert_not_called()
    
    def test_wrapper_allows_dietary_on_web(self):
        """Dietary summary should work normally on web."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_fn = MagicMock(return_value={"status": "success", "data": "sensitive"})
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "get_family_dietary_summary",
            channel="web"
        )
        result = wrapped({}, None, None, None)
        
        assert result["status"] == "success"
        original_fn.assert_called_once()
    
    def test_wrapper_blocks_household_members_on_telegram(self):
        """Household members should be blocked on Telegram."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_fn = MagicMock(return_value={"status": "success"})
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "get_household_members",
            channel="telegram"
        )
        result = wrapped({}, None, None, None)
        
        assert result["status"] == "restricted"
        assert "dashboard" in result["message"].lower()
    
    def test_wrapper_blocks_on_line_channel(self):
        """Sensitive tools should also be blocked on LINE."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_fn = MagicMock(return_value={"status": "success"})
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "get_family_dietary_summary",
            channel="line"
        )
        result = wrapped({}, None, None, None)
        
        assert result["status"] == "restricted"
    
    def test_non_sensitive_tool_not_wrapped(self):
        """Non-sensitive tools should pass through unchanged."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_fn = MagicMock(return_value={"status": "success", "orders": []})
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "get_family_order_history",  # Not sensitive
            channel="telegram"
        )
        result = wrapped({}, None, None, None)
        
        assert result["status"] == "success"
        original_fn.assert_called_once()
    
    def test_redirect_message_is_helpful(self):
        """Redirect messages should tell user where to find the data."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_fn = MagicMock()
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "get_family_dietary_summary",
            channel="telegram"
        )
        result = wrapped({}, None, None, None)
        
        message = result["message"].lower()
        # Should mention dashboard or web app
        assert "dashboard" in message or "web" in message
        # Should mention what data they're looking for
        assert "dietary" in message or "allerg" in message


class TestRecipeCompliancePartialData:
    """Phase 4: Recipe compliance should give yes/no without exposing names."""
    
    def test_compliance_telegram_no_names_in_response(self):
        """Recipe compliance on Telegram should not expose member names."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        # Original function would return names in issues
        original_fn = MagicMock(return_value={
            "status": "success",
            "is_compliant": False,
            "issues": ["⚠️ ALLERGEN ALERT: 'peanut butter' contains peanuts (Sarah is allergic)"],
            "member_details": [{"name": "Sarah", "allergies": ["peanuts"]}]
        })
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "check_recipe_compliance",
            channel="telegram"
        )
        result = wrapped({"ingredients": ["peanut butter"]}, None, None, None)
        
        # Should still indicate compliance status
        assert "is_compliant" in result or result["status"] == "restricted"
        
        # Should NOT contain the name "Sarah"
        result_str = str(result)
        assert "Sarah" not in result_str
    
    def test_compliance_web_includes_full_details(self):
        """Recipe compliance on web should include full details."""
        from chefs.services.sous_chef.tools.sensitive_wrapper import (
            wrap_sensitive_tool
        )
        
        original_result = {
            "status": "success",
            "is_compliant": False,
            "issues": ["⚠️ ALLERGEN ALERT: 'peanut butter' contains peanuts (Sarah is allergic)"],
        }
        original_fn = MagicMock(return_value=original_result)
        
        wrapped = wrap_sensitive_tool(
            original_fn,
            "check_recipe_compliance",
            channel="web"
        )
        result = wrapped({"ingredients": ["peanut butter"]}, None, None, None)
        
        # Should have full details including name
        assert result == original_result
        assert "Sarah" in str(result)


class TestToolLoaderIntegration:
    """Phase 3: Test that loader properly wraps sensitive tools."""
    
    def test_loader_returns_sensitive_tools_for_telegram(self):
        """Tool loader should include sensitive tools for Telegram (they get wrapped at execution)."""
        from chefs.services.sous_chef.tools.loader import get_tool_schemas_for_channel
        
        tools = get_tool_schemas_for_channel("telegram")
        tool_names = [t.get("function", {}).get("name") or t.get("name") for t in tools]
        
        # Sensitive tools should still be in the list (wrapped at execution time)
        assert "get_family_dietary_summary" in tool_names
        assert "check_recipe_compliance" in tool_names
    
    def test_execute_tool_respects_channel_for_sensitive(self):
        """execute_tool should respect channel restrictions for sensitive tools."""
        from chefs.services.sous_chef.tools.loader import execute_tool
        from unittest.mock import MagicMock
        
        # Mock chef and customer
        mock_chef = MagicMock()
        mock_customer = MagicMock()
        mock_customer.dietary_preferences.all.return_value = []
        mock_customer.allergies = ["peanuts"]
        mock_customer.custom_allergies = []
        mock_customer.first_name = "Michael"
        mock_customer.username = "michael"
        mock_customer.household_member_count = 1
        mock_customer.household_members.all.return_value = []
        
        # Execute on Telegram - should be restricted
        result = execute_tool(
            "get_family_dietary_summary",
            args={},
            chef=mock_chef,
            customer=mock_customer,
            lead=None,
            channel="telegram"
        )
        
        assert result["status"] == "restricted"
        assert "Michael" not in str(result)
    
    def test_execute_tool_allows_sensitive_on_web(self):
        """execute_tool should allow sensitive tools on web."""
        from chefs.services.sous_chef.tools.loader import execute_tool
        from unittest.mock import MagicMock
        
        mock_chef = MagicMock()
        mock_customer = MagicMock()
        mock_customer.dietary_preferences.all.return_value = []
        mock_customer.allergies = ["peanuts"]
        mock_customer.custom_allergies = []
        mock_customer.first_name = "Michael"
        mock_customer.username = "michael"
        mock_customer.household_member_count = 1
        mock_customer.household_members.all.return_value = []
        
        # Execute on web - should work
        result = execute_tool(
            "get_family_dietary_summary",
            args={},
            chef=mock_chef,
            customer=mock_customer,
            lead=None,
            channel="web"
        )
        
        assert result["status"] == "success"
        # Should contain actual data
        assert "all_allergies_must_avoid" in result or "member_details" in result


class TestServiceIntegration:
    """Integration test: Service layer respects sensitive data rules."""

    @pytest.mark.django_db
    def test_service_telegram_blocks_dietary_tool(self):
        """SousChefService on Telegram should block sensitive tool results."""
        # This is an integration test - will be implemented after unit tests pass
        pass

    @pytest.mark.django_db
    def test_service_web_allows_dietary_tool(self):
        """SousChefService on web should allow sensitive tool results."""
        # This is an integration test - will be implemented after unit tests pass
        pass


class TestAntiSolicitationPrompts:
    """Tests for anti-solicitation rules in channel prompts."""

    def test_telegram_prompt_includes_anti_solicitation_rules(self):
        """Verify Telegram prompt prohibits asking for PII."""
        from chefs.services.sous_chef.prompts.builder import get_channel_context

        telegram_context = get_channel_context("telegram")

        # Check anti-solicitation language is present
        assert "DO NOT" in telegram_context
        assert "ask" in telegram_context.lower()
        assert "tell" in telegram_context.lower() or "let me know" in telegram_context.lower()

    def test_line_prompt_includes_anti_solicitation_rules(self):
        """Verify LINE prompt prohibits asking for PII."""
        from chefs.services.sous_chef.prompts.builder import get_channel_context

        line_context = get_channel_context("line")

        assert "DO NOT" in line_context
        assert "ask" in line_context.lower()

    def test_telegram_prompt_includes_meal_planning_guidance(self):
        """Verify Telegram prompt includes meal planning guidance."""
        from chefs.services.sous_chef.prompts.builder import get_channel_context

        telegram_context = get_channel_context("telegram")

        assert "MealPlanningGuidance" in telegram_context
        assert "general" in telegram_context.lower()

    def test_line_prompt_includes_meal_planning_guidance(self):
        """Verify LINE prompt includes meal planning guidance."""
        from chefs.services.sous_chef.prompts.builder import get_channel_context

        line_context = get_channel_context("line")

        assert "MealPlanningGuidance" in line_context


class TestPIIDetector:
    """Tests for incoming PII detection."""

    def test_pii_detector_catches_allergy_mentions(self):
        """Verify PII detector identifies allergy information."""
        from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

        test_cases = [
            ("they're allergic to peanuts", True, "allergy"),
            ("the family has a nut allergy", True, "allergy"),
            ("she can't eat dairy", True, "restriction"),
            ("he's celiac", True, "medical_condition"),
            ("they're vegan", True, "dietary_preference"),
            ("what time is the delivery?", False, None),
            ("let's do chicken for dinner", False, None),
        ]

        for message, expected_pii, expected_type in test_cases:
            has_pii, pii_type = detect_health_pii(message)
            assert has_pii == expected_pii, f"Failed for: {message}"
            if expected_type:
                assert pii_type == expected_type, f"Wrong type for: {message}"

    def test_pii_detector_catches_intolerance(self):
        """Verify PII detector identifies intolerance mentions."""
        from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

        has_pii, pii_type = detect_health_pii("she's lactose intolerant")
        assert has_pii is True
        assert pii_type == "intolerance"

    def test_pii_detector_catches_medical_conditions(self):
        """Verify PII detector identifies medical conditions."""
        from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

        conditions = ["he has diabetes", "she has crohn's", "they have ibs"]
        for message in conditions:
            has_pii, pii_type = detect_health_pii(message)
            assert has_pii is True, f"Failed for: {message}"
            assert pii_type == "medical_condition", f"Wrong type for: {message}"

    def test_pii_detector_catches_dietary_preferences(self):
        """Verify PII detector identifies dietary preferences."""
        from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

        prefs = ["they're vegetarian", "she's pescatarian", "kosher meals only"]
        for message in prefs:
            has_pii, pii_type = detect_health_pii(message)
            assert has_pii is True, f"Failed for: {message}"
            assert pii_type == "dietary_preference", f"Wrong type for: {message}"

    def test_pii_detector_catches_free_from(self):
        """Verify PII detector identifies 'free from' mentions."""
        from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

        free_from = ["they need gluten-free", "dairy free please", "nut-free options"]
        for message in free_from:
            has_pii, pii_type = detect_health_pii(message)
            assert has_pii is True, f"Failed for: {message}"
            assert pii_type == "free_from", f"Wrong type for: {message}"

    def test_pii_ignored_on_telegram(self):
        """Verify PII in messages is flagged for ignoring on Telegram."""
        from chefs.services.sous_chef.filters.pii_detector import should_ignore_pii_in_message

        # Should ignore on Telegram
        assert should_ignore_pii_in_message("they're allergic to nuts", "telegram") is True

        # Should NOT ignore on web (full access)
        assert should_ignore_pii_in_message("they're allergic to nuts", "web") is False

    def test_pii_ignored_on_line(self):
        """Verify PII in messages is flagged for ignoring on LINE."""
        from chefs.services.sous_chef.filters.pii_detector import should_ignore_pii_in_message

        assert should_ignore_pii_in_message("she's lactose intolerant", "line") is True

    def test_non_pii_not_ignored(self):
        """Verify non-PII messages are not flagged."""
        from chefs.services.sous_chef.filters.pii_detector import should_ignore_pii_in_message

        # Even on Telegram, normal messages should not be ignored
        assert should_ignore_pii_in_message("what time is the delivery?", "telegram") is False
        assert should_ignore_pii_in_message("let's plan some meals", "telegram") is False
