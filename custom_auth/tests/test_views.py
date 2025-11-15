from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from custom_auth.models import CustomUser, Address
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.core.cache import cache
from rest_framework.test import APIClient
from django.conf import settings
from django.urls import clear_url_caches
from importlib import reload
from copy import deepcopy


def _ensure_test_mode_urls():
    if not getattr(settings, "TEST_MODE", False):
        settings.TEST_MODE = True
        clear_url_caches()
        from custom_auth import urls as auth_urls  # local import to avoid circular refs
        from hood_united import urls as project_urls
        reload(auth_urls)
        reload(project_urls)


_ensure_test_mode_urls()


_THROTTLE_TEST_REST_FRAMEWORK = deepcopy(settings.REST_FRAMEWORK)
_THROTTLE_TEST_REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = [
    'rest_framework.throttling.AnonRateThrottle',
    'rest_framework.throttling.UserRateThrottle',
]
_THROTTLE_TEST_REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    **_THROTTLE_TEST_REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
    'anon': '10/day',
    'user': '2/min',
    'auth_burst': '2/min',
    'auth_daily': '5/day',
}

@override_settings(TEST_MODE=True)
class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('custom_auth:login')
        self.user = get_user_model().objects.create_user(username='testuser', password='12345')

    def test_login_success(self):
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': '12345'
        })
        user = get_user_model().objects.get(username='testuser')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(user.is_authenticated)


@override_settings(TEST_MODE=True)
class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('custom_auth:register')

    def test_register_success(self):
        response = self.client.post(self.register_url, {
            'username': 'testuser',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'email': 'test@test.com',
            # ---- address fields added for RegisterView -----------------
            'street': '123 test st',
            'city': 'Test city',
            'state': 'TS',
            'input_postalcode': '12345',
            'country': 'US',
        })
        user = get_user_model().objects.filter(username='testuser').first()
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(user)


@override_settings(TEST_MODE=True)
class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Creating a test user here. You can adjust the fields as per your user model.
        self.test_user = CustomUser.objects.create_user(
            username='testuser',
            password='12345',
            email='test@test.com',
            initial_email_confirmed=True,  # Setting email confirmed to access profile
        )
        
        # Creating a test address for the test user
        self.test_address = Address.objects.create(
            user=self.test_user,
            street='123 test st',
            city='Test city',
            state='TS',
            country='US',
            input_postalcode='12345'
        )

        self.profile_url = reverse('custom_auth:profile')

    def test_logged_in_user_can_access_profile_page(self):
        self.client.login(username='testuser', password='12345')
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'custom_auth/profile.html')
        self.assertContains(response, 'testuser')  # Check if username is in the response
        self.assertContains(response, '123 test st')  # Check if user's address is in the response


@override_settings(TEST_MODE=True)
class AuthProfileThrottleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='throttleuser',
            password='testpass123',
            email='throttle@example.com',
        )
        self.address = Address.objects.create(
            user=self.user,
            street='1 Test Way',
            city='Testville',
            state='TS',
            input_postalcode='00000',
            country='US',
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        cache.clear()

    @override_settings(REST_FRAMEWORK=_THROTTLE_TEST_REST_FRAMEWORK)
    def test_user_details_not_throttled_for_authenticated_user(self):
        cache.clear()
        url = reverse('custom_auth:user_details')

        for attempt in range(5):
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                msg=f"Expected 200, got {response.status_code} on attempt {attempt + 1}",
            )

    @override_settings(REST_FRAMEWORK=_THROTTLE_TEST_REST_FRAMEWORK)
    def test_address_details_not_throttled_for_authenticated_user(self):
        cache.clear()
        url = reverse('custom_auth:address_details')

        for attempt in range(5):
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                200,
                msg=f"Expected 200, got {response.status_code} on attempt {attempt + 1}",
            )

    def test_update_profile_uses_profile_mutation_throttles(self):
        from custom_auth import views as auth_views
        from custom_auth.throttles import AuthenticatedBurstThrottle, AuthenticatedDailyThrottle

        throttle_classes = list(getattr(auth_views.update_profile_api.cls, 'throttle_classes', []))
        self.assertEqual(throttle_classes, [AuthenticatedBurstThrottle, AuthenticatedDailyThrottle])

    def test_user_details_view_has_no_throttles(self):
        from custom_auth import views as auth_views

        throttle_classes = list(getattr(auth_views.user_details_view.cls, 'throttle_classes', []))
        self.assertEqual(throttle_classes, [])

    def test_address_details_view_has_no_throttles(self):
        from custom_auth import views as auth_views

        throttle_classes = list(getattr(auth_views.address_details_view.cls, 'throttle_classes', []))
        self.assertEqual(throttle_classes, [])
