from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
import json
import os

from custom_auth.models import OnboardingSession, Address, CustomUser
from meals.models import CustomDietaryPreference


class OnboardingCompleteRegistrationTests(TestCase):
    """Comprehensive tests for the `onboarding_complete_registration` API endpoint."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('custom_auth:secure_onboarding_complete')

        # Ensure env vars used by the view exist so requests.post is called with a valid URL
        os.environ.setdefault('STREAMLIT_URL', 'http://testserver')
        os.environ.setdefault('N8N_REGISTER_URL', 'http://example.com')
        os.environ.setdefault('N8N_TRACEBACK_URL', 'http://example.com')

        # ------------------------------------------------------------------
        # Patch external side-effects (HTTP & Celery tasks) for ALL tests
        # ------------------------------------------------------------------
        self.patcher_requests = patch('hood_united.custom_auth.views.requests.post')
        self.mock_requests_post = self.patcher_requests.start()
        self.mock_requests_post.return_value.status_code = 200  # Simulate OK response

        self.patcher_celery = patch('hood_united.custom_auth.views.handle_custom_dietary_preference.delay')
        self.mock_celery = self.patcher_celery.start()

    def tearDown(self):
        self.patcher_requests.stop()
        self.patcher_celery.stop()

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _create_onboarding_session(self, guest_id: str, data: dict):
        """Convenience wrapper to create an OnboardingSession object."""
        return OnboardingSession.objects.create(guest_id=guest_id, data=data, completed=False)

    def _post(self, guest_id: str, password: str = 'Passw0rd!'):
        """Helper to perform the POST request with JSON body."""
        return self.client.post(
            self.url,
            data=json.dumps({'guest_id': guest_id, 'password': password}),
            content_type='application/json',
        )

    # ------------------------------------------------------------------
    #  Positive path
    # ------------------------------------------------------------------
    def test_complete_registration_success_minimal(self):
        """Minimal happy-path: username + email stored, password supplied."""
        guest_id = 'guest123'
        stored_data = {
            'username': 'testguest',
            'email': 'guest@example.com',
        }
        self._create_onboarding_session(guest_id, stored_data)

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)

        payload = resp.json()
        self.assertIn('refresh', payload)
        self.assertIn('access', payload)
        self.assertEqual(payload['status'], 'User registered successfully through onboarding')

        # User should now exist in DB
        user = get_user_model().objects.filter(username='testguest').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'guest@example.com')

    # ------------------------------------------------------------------
    #  Error handling & validations
    # ------------------------------------------------------------------
    def test_missing_guest_id(self):
        resp = self.client.post(
            self.url, data=json.dumps({'password': 'Passw0rd!'}), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Guest ID is required', resp.json()['errors'])

    def test_missing_password(self):
        guest_id = 'guest_missing_pw'
        self._create_onboarding_session(guest_id, {'username': 'missingpw', 'email': 'missingpw@test.com'})
        resp = self.client.post(
            self.url, data=json.dumps({'guest_id': guest_id}), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Password is required', resp.json()['errors'])

    def test_duplicate_username_or_email(self):
        # Pre-create an actual user with a username/email that the onboarding session will reuse
        get_user_model().objects.create_user(username='dupuser', email='dup@example.com', password='irrelevant')
        guest_id = 'guest_dup'
        self._create_onboarding_session(guest_id, {'username': 'dupuser', 'email': 'dup@example.com'})

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 400)
        errors = resp.json()['errors']
        # The view checks username first, so expect that error
        self.assertIn('already taken', errors)

    # ------------------------------------------------------------------
    #  Optional fields & robustness
    # ------------------------------------------------------------------
    def test_invalid_address_is_safely_skipped(self):
        """If address validation fails, user should still be created and no Address row saved."""
        guest_id = 'guest_bad_addr'
        stored_data = {
            'username': 'badaddruser',
            'email': 'badaddr@example.com',
            # --- deliberately invalid US postal code (too short) ---
            'street': '123 Test St',
            'city': 'Nowhere',
            'state': 'CA',
            'country': 'US',
            'postalcode': '123',
        }
        self._create_onboarding_session(guest_id, stored_data)

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)

        user = CustomUser.objects.get(username='badaddruser')
        # Address should NOT exist because serializer would have failed validation
        self.assertFalse(Address.objects.filter(user=user).exists())

    def test_custom_dietary_preferences_are_created_and_linked(self):
        guest_id = 'guest_custdiet'
        stored_data = {
            'username': 'custdietuser',
            'email': 'custdiet@example.com',
            'custom_dietary_preferences': ['Carnivore', 'Fruit-Only'],
        }
        self._create_onboarding_session(guest_id, stored_data)

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)
        user = CustomUser.objects.get(username='custdietuser')

        # The preferences should now exist in the DB
        self.assertTrue(CustomDietaryPreference.objects.filter(name='Carnivore').exists())
        self.assertTrue(CustomDietaryPreference.objects.filter(name='Fruit-Only').exists())

        # And be linked to the user
        user_pref_names = list(user.custom_dietary_preferences.values_list('name', flat=True))
        self.assertCountEqual(user_pref_names, ['Carnivore', 'Fruit-Only'])

    def test_valid_us_address_is_saved(self):
        guest_id = 'guest_us_addr'
        stored_data = {
            'username': 'usaddruser',
            'email': 'usaddr@example.com',
            'street': '1600 Amphitheatre Pkwy',
            'city': 'Mountain View',
            'state': 'CA',
            'country': 'US',
            'postalcode': '94043',  # Valid 5-digit ZIP
        }
        self._create_onboarding_session(guest_id, stored_data)

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)
        user = CustomUser.objects.get(username='usaddruser')
        address = Address.objects.get(user=user)
        self.assertEqual(address.input_postalcode, '94043')  # Already normalized
        self.assertEqual(address.display_postalcode, '94043')
        self.assertEqual(str(address.country), 'US')

    def test_valid_canadian_address_normalizes_postal_code(self):
        guest_id = 'guest_ca_addr'
        stored_data = {
            'username': 'caaddruser',
            'email': 'caaddr@example.com',
            'street': '111 Wellington St',
            'city': 'Ottawa',
            'state': 'ON',
            'country': 'CA',
            'postalcode': 'K1A 0B1',  # Valid Canadian format with space
        }
        self._create_onboarding_session(guest_id, stored_data)
        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)
        user = CustomUser.objects.get(username='caaddruser')
        address = Address.objects.get(user=user)
        # Should be normalized (spaces removed, upper-case)
        self.assertEqual(address.input_postalcode, 'K1A0B1')
        self.assertEqual(address.display_postalcode, 'K1A 0B1')
        self.assertEqual(str(address.country), 'CA')

    def test_valid_japanese_address_normalizes_postal_code(self):
        guest_id = 'guest_jp_addr'
        stored_data = {
            'username': 'jpaddruser',
            'email': 'jpaddr@example.com',
            'street': '1-1 Chiyoda',
            'city': 'Tokyo',
            'state': 'Tokyo',
            'country': 'JP',
            'postalcode': '100-0001',  # Typical JP format with hyphen
        }
        self._create_onboarding_session(guest_id, stored_data)
        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)
        user = CustomUser.objects.get(username='jpaddruser')
        address = Address.objects.get(user=user)
        self.assertEqual(address.input_postalcode, '1000001')
        self.assertEqual(address.display_postalcode, '100-0001')  # original preserved
        self.assertEqual(str(address.country), 'JP')

    def test_onboarding_session_marked_completed(self):
        guest_id = 'guest_complete_flag'
        stored_data = {
            'username': 'completeflaguser',
            'email': 'completeflag@example.com',
        }
        session = self._create_onboarding_session(guest_id, stored_data)
        self.assertFalse(session.completed)

        resp = self._post(guest_id)
        self.assertEqual(resp.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.completed) 