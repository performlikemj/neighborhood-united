# chefs/services/sous_chef/tests/conftest.py
"""Shared fixtures for Sous Chef tests."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def test_user(db):
    """Create a test user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="testchef",
        first_name="Mario",
        last_name="Chef",
        email="test@example.com",
        password="testpass123"
    )


@pytest.fixture
def test_chef(db, test_user):
    """Create a test chef."""
    from chefs.models import Chef
    return Chef.objects.create(user=test_user)


@pytest.fixture
def test_customer(db):
    """Create a test customer."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="testcustomer",
        first_name="John",
        last_name="Doe",
        email="customer@example.com",
        password="testpass123"
    )


@pytest.fixture
def telegram_link(db, test_chef):
    """Create a Telegram link for test chef."""
    from chefs.models.telegram_integration import ChefTelegramLink
    return ChefTelegramLink.objects.create(
        chef=test_chef,
        telegram_user_id=12345,
        telegram_username="testchef",
        is_active=True
    )


@pytest.fixture
def mock_groq():
    """Mock Groq client with standard response."""
    with patch("chefs.services.sous_chef.service.Groq") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        
        # Standard response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, Chef! How can I help?"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        
        yield mock_client


@pytest.fixture
def mock_groq_with_tool_call():
    """Mock Groq client that returns a tool call."""
    with patch("chefs.services.sous_chef.service.Groq") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        
        # First response with tool call
        tool_response = MagicMock()
        tool_response.choices = [MagicMock()]
        tool_response.choices[0].message.content = ""
        tool_response.choices[0].message.tool_calls = [MagicMock()]
        tool_response.choices[0].message.tool_calls[0].id = "call_123"
        tool_response.choices[0].message.tool_calls[0].function.name = "get_upcoming_family_orders"
        tool_response.choices[0].message.tool_calls[0].function.arguments = "{}"
        
        # Second response (final)
        final_response = MagicMock()
        final_response.choices = [MagicMock()]
        final_response.choices[0].message.content = "You have 3 orders this week."
        final_response.choices[0].message.tool_calls = None
        
        mock_client.chat.completions.create.side_effect = [tool_response, final_response]
        
        yield mock_client
