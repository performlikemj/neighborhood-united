"""
Tests for Sous Chef Workspace API.

Tests cover:
- GET creates workspace with defaults
- GET returns existing workspace
- Non-chef users are forbidden
- PATCH partial updates
- POST reset to defaults

Run with: pytest chefs/tests/test_workspace_api.py -v
"""

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from custom_auth.models import CustomUser
from chefs.models import Chef, ChefWorkspace


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class WorkspaceApiSecurityTests(TestCase):
    """Tests for authentication and authorization security."""

    def setUp(self):
        self.client = APIClient()

        # Create a regular customer (non-chef)
        self.customer = CustomUser.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="testpass123",
        )

        # Create a chef user
        self.chef_user = CustomUser.objects.create_user(
            username="chefmike",
            email="chef@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")

    def _authenticate(self, user=None):
        if user is None:
            self.client.force_authenticate(user=None)
        else:
            self.client.force_authenticate(user=user)

    def test_workspace_get_requires_authentication(self):
        """Workspace GET endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_workspace')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [401, 403])

    def test_workspace_update_requires_authentication(self):
        """Workspace PATCH endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {"soul_prompt": "test"}, format='json')
        self.assertIn(resp.status_code, [401, 403])

    def test_workspace_reset_requires_authentication(self):
        """Workspace POST reset endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {}, format='json')
        self.assertIn(resp.status_code, [401, 403])

    def test_workspace_get_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from accessing workspace."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_workspace')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.data)

    def test_workspace_update_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from updating workspace."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {"soul_prompt": "test"}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_workspace_reset_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from resetting workspace."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 403)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class WorkspaceGetTests(TestCase):
    """Tests for workspace GET endpoint."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chefmike",
            email="chef@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

    def test_get_creates_workspace_with_defaults(self):
        """GET should create workspace with defaults if it doesn't exist."""
        # Ensure no workspace exists
        self.assertFalse(ChefWorkspace.objects.filter(chef=self.chef).exists())

        url = reverse('chefs:chef_workspace')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)

        # Workspace should now exist
        self.assertTrue(ChefWorkspace.objects.filter(chef=self.chef).exists())

        # Check default soul prompt is populated
        self.assertIn("Sous Chef", resp.data['soul_prompt'])
        self.assertEqual(resp.data['business_rules'], '')
        self.assertIsInstance(resp.data['enabled_tools'], list)
        self.assertTrue(len(resp.data['enabled_tools']) > 0)
        self.assertTrue(resp.data['include_analytics'])
        self.assertTrue(resp.data['include_seasonal'])
        self.assertTrue(resp.data['auto_memory_save'])

    def test_get_returns_existing_workspace(self):
        """GET should return existing workspace without modification."""
        # Pre-create workspace with custom values
        workspace = ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt="Custom personality",
            business_rules="No orders after 8pm",
            enabled_tools=['tool_a', 'tool_b'],
            include_analytics=False,
        )

        url = reverse('chefs:chef_workspace')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['soul_prompt'], "Custom personality")
        self.assertEqual(resp.data['business_rules'], "No orders after 8pm")
        self.assertEqual(resp.data['enabled_tools'], ['tool_a', 'tool_b'])
        self.assertEqual(resp.data['include_analytics'], False)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class WorkspaceUpdateTests(TestCase):
    """Tests for workspace PATCH update endpoint."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chefmike",
            email="chef@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

        # Pre-create workspace
        self.workspace = ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt="Original prompt",
            business_rules="Original rules",
        )

    def test_partial_update_soul_prompt_only(self):
        """PATCH should update only provided fields."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {
            "soul_prompt": "New custom personality"
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertEqual(resp.data['updated_fields'], ['soul_prompt'])
        self.assertEqual(resp.data['soul_prompt'], "New custom personality")
        # Business rules should remain unchanged
        self.assertEqual(resp.data['business_rules'], "Original rules")

        # Verify in database
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.soul_prompt, "New custom personality")
        self.assertEqual(self.workspace.business_rules, "Original rules")

    def test_partial_update_business_rules_only(self):
        """PATCH should update business_rules without affecting other fields."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {
            "business_rules": "No orders on Sundays"
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated_fields'], ['business_rules'])
        self.assertEqual(resp.data['business_rules'], "No orders on Sundays")
        self.assertEqual(resp.data['soul_prompt'], "Original prompt")

    def test_partial_update_multiple_fields(self):
        """PATCH should update multiple fields at once."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {
            "soul_prompt": "Friendly and casual",
            "business_rules": "Hours: 9am-6pm",
            "include_analytics": False,
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('soul_prompt', resp.data['updated_fields'])
        self.assertIn('business_rules', resp.data['updated_fields'])
        self.assertIn('include_analytics', resp.data['updated_fields'])
        self.assertEqual(resp.data['soul_prompt'], "Friendly and casual")
        self.assertEqual(resp.data['business_rules'], "Hours: 9am-6pm")
        self.assertEqual(resp.data['include_analytics'], False)

    def test_update_enabled_tools(self):
        """PATCH should update enabled_tools list."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {
            "enabled_tools": ["get_family_dietary_summary", "search_chef_dishes"]
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['enabled_tools'], [
            "get_family_dietary_summary", "search_chef_dishes"
        ])

    def test_update_with_empty_body_returns_success(self):
        """PATCH with empty body should succeed with no updates."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated_fields'], [])

    def test_update_ignores_unknown_fields(self):
        """PATCH should ignore fields not in allowed list."""
        url = reverse('chefs:chef_workspace_update')
        resp = self.client.patch(url, {
            "soul_prompt": "Updated",
            "unknown_field": "should be ignored",
            "chef_id": 999,  # Should not be updatable
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated_fields'], ['soul_prompt'])


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class WorkspaceResetTests(TestCase):
    """Tests for workspace POST reset endpoint."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chefmike",
            email="chef@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

        # Pre-create workspace with custom values
        self.workspace = ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt="Custom personality",
            business_rules="Custom rules",
            enabled_tools=['custom_tool'],
            include_analytics=False,
        )

    def test_reset_defaults_to_soul_prompt_and_business_rules(self):
        """POST reset without fields resets soul_prompt and business_rules."""
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertIn('soul_prompt', resp.data['reset_fields'])
        self.assertIn('business_rules', resp.data['reset_fields'])

        # soul_prompt should be reset to default
        self.assertIn("Sous Chef", resp.data['soul_prompt'])
        # business_rules should be empty string (default)
        self.assertEqual(resp.data['business_rules'], '')

        # enabled_tools should NOT be reset
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.enabled_tools, ['custom_tool'])

    def test_reset_specific_fields(self):
        """POST reset with specific fields resets only those fields."""
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {
            "fields": ["soul_prompt"]
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reset_fields'], ['soul_prompt'])
        self.assertIn("Sous Chef", resp.data['soul_prompt'])
        # business_rules should remain unchanged
        self.assertEqual(resp.data['business_rules'], "Custom rules")

    def test_reset_enabled_tools(self):
        """POST reset can reset enabled_tools to defaults."""
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {
            "fields": ["enabled_tools"]
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('enabled_tools', resp.data['reset_fields'])

        # Should have default tools
        default_tools = ChefWorkspace.get_default_tools()
        self.assertEqual(resp.data['enabled_tools'], default_tools)

    def test_reset_all_fields(self):
        """POST reset can reset all workspace fields."""
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {
            "fields": [
                "soul_prompt",
                "business_rules",
                "enabled_tools",
                "include_analytics",
                "include_seasonal",
                "auto_memory_save"
            ]
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['reset_fields']), 6)

        # Verify all defaults
        self.assertIn("Sous Chef", resp.data['soul_prompt'])
        self.assertEqual(resp.data['business_rules'], '')
        self.assertTrue(resp.data['include_analytics'])
        self.assertTrue(resp.data['include_seasonal'])
        self.assertTrue(resp.data['auto_memory_save'])

    def test_reset_ignores_unknown_fields(self):
        """POST reset ignores unknown field names."""
        url = reverse('chefs:chef_workspace_reset')
        resp = self.client.post(url, {
            "fields": ["soul_prompt", "unknown_field", "chef_id"]
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        # Only soul_prompt should be reset
        self.assertEqual(resp.data['reset_fields'], ['soul_prompt'])


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class WorkspaceIsolationTests(TestCase):
    """Tests for data isolation between chefs."""

    def setUp(self):
        self.client = APIClient()

        # Create two chefs
        self.chef_user_1 = CustomUser.objects.create_user(
            username="chef1",
            email="chef1@example.com",
            password="testpass123",
        )
        self.chef_1 = Chef.objects.create(user=self.chef_user_1)

        self.chef_user_2 = CustomUser.objects.create_user(
            username="chef2",
            email="chef2@example.com",
            password="testpass123",
        )
        self.chef_2 = Chef.objects.create(user=self.chef_user_2)

        # Create workspace for chef 1
        self.workspace_1 = ChefWorkspace.objects.create(
            chef=self.chef_1,
            soul_prompt="Chef 1 personality",
            business_rules="Chef 1 rules",
        )

    def test_chef_cannot_access_other_chef_workspace(self):
        """Each chef can only access their own workspace."""
        # Authenticate as chef 2
        self.client.force_authenticate(user=self.chef_user_2)

        url = reverse('chefs:chef_workspace')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        # Should get their own (newly created) workspace, not chef 1's
        self.assertNotEqual(resp.data['soul_prompt'], "Chef 1 personality")

    def test_chef_update_isolated_to_own_workspace(self):
        """Updates only affect the authenticated chef's workspace."""
        # Authenticate as chef 2
        self.client.force_authenticate(user=self.chef_user_2)

        # First GET to create chef 2's workspace
        url = reverse('chefs:chef_workspace')
        self.client.get(url)

        # Update chef 2's workspace
        update_url = reverse('chefs:chef_workspace_update')
        self.client.patch(update_url, {
            "soul_prompt": "Chef 2 personality"
        }, format='json')

        # Verify chef 1's workspace is unchanged
        self.workspace_1.refresh_from_db()
        self.assertEqual(self.workspace_1.soul_prompt, "Chef 1 personality")
