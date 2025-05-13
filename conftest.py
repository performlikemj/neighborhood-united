import os
import pytest
from unittest.mock import patch, MagicMock
import django
from django.conf import settings

# Configure Django settings before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')
django.setup()

# Create a mock OpenAI client for tests
@pytest.fixture(autouse=True)
def mock_openai_client():
    """
    Mock the OpenAI client to prevent API calls during testing.
    This is applied automatically to all tests.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"dietary_preferences": ["Vegetarian", "Gluten-Free"]}'
                )
            )
        ]
    )
    
    with patch('openai.OpenAI', return_value=mock_client):
        yield mock_client 