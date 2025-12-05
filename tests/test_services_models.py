import pytest
from django.contrib.auth import get_user_model

from chefs.models import Chef


@pytest.fixture
def chef(db):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='chefuser', email='chef@example.com', password='pass1234'
    )
    return Chef.objects.create(user=user)


def test_service_offering_defaults_requires_services_app(chef):
    from services.models import ServiceOffering  # noqa: F401


def test_service_tier_defaults(chef):
    from services.models import ServiceOffering, ServiceTier

    offering = ServiceOffering.objects.create(
        chef=chef,
        title='Weekly Prep',
        service_type='weekly_prep',
        description='Prep meals each Sunday',
    )

    tier = ServiceTier.objects.create(
        offering=offering,
        display_label='Family Plan',
        household_min=2,
        desired_unit_amount_cents=25000,
    )

    assert tier.household_min == 2
    assert tier.household_max is None
    assert tier.desired_unit_amount_cents == 25000
    assert tier.is_recurring is False
    assert tier.recurrence_interval == ''
    assert tier.duration_minutes is None
    assert tier.hidden is False
    assert tier.soft_deleted is False
    assert tier.sort_order == 0
    assert offering.tiers.count() == 1
