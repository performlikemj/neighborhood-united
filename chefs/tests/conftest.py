# chefs/tests/conftest.py
"""
Pytest fixtures for chefs app tests.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testchefuser',
        email='chef@test.com',
        password='testpass123'
    )


@pytest.fixture
def customer(db):
    """Create a test customer user."""
    return User.objects.create_user(
        username='testcustomer',
        email='customer@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Customer'
    )


@pytest.fixture
def chef(db, user):
    """Create a test chef."""
    from chefs.models import Chef
    
    chef, _ = Chef.objects.get_or_create(user=user)
    return chef


@pytest.fixture
def lead(db, chef):
    """Create a test lead."""
    from crm.models import Lead
    
    lead = Lead.objects.create(
        chef=chef,
        first_name='Test',
        last_name='Lead',
        email='lead@test.com',
        status='new'
    )
    return lead


@pytest.fixture
def client_context(db, chef, customer):
    """Create a test ClientContext."""
    from chefs.models import ClientContext
    
    context, _ = ClientContext.objects.get_or_create(
        chef=chef,
        client=customer
    )
    return context


@pytest.fixture
def proactive_settings(db, chef):
    """Create proactive settings for chef."""
    from chefs.models import ChefProactiveSettings
    
    settings, _ = ChefProactiveSettings.objects.get_or_create(chef=chef)
    return settings


@pytest.fixture
def onboarding_state(db, chef):
    """Create onboarding state for chef."""
    from chefs.models import ChefOnboardingState
    
    state, _ = ChefOnboardingState.objects.get_or_create(chef=chef)
    return state
