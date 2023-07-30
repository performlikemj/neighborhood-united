from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from custom_auth.models import CustomUser, Address
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes

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
        })
        user = get_user_model().objects.filter(username='testuser').first()
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['test@test.com'])


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
            zipcode='12345'
        )

        self.profile_url = reverse('custom_auth:profile')

    def test_logged_in_user_can_access_profile_page(self):
        self.client.login(username='testuser', password='12345')
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'custom_auth/profile.html')
        self.assertContains(response, 'testuser')  # Check if username is in the response
        self.assertContains(response, '123 test st')  # Check if user's address is in the response


