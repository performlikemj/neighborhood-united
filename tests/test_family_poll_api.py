from django.apps import apps
from rest_framework.test import APIClient
import pytest


@pytest.fixture
def api_client():
    return APIClient()


def test_family_poll_app_is_not_installed():
    assert not apps.is_installed("family_poll")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/family-poll/"),
        ("get", "/family-poll/auth"),
        ("get", "/family-poll/auth/"),
        ("post", "/family-poll/auth/"),
        ("get", "/family-poll/votes"),
        ("get", "/family-poll/votes/"),
        ("post", "/family-poll/votes/"),
        ("post", "/family-poll/vote/"),
    ],
)
def test_family_poll_routes_return_404(api_client, method, path):
    response = getattr(api_client, method)(path, format="json")
    assert response.status_code == 404
