import tempfile
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image

from custom_auth.models import CustomUser, UserRole
from chefs.models import Chef, ChefPhoto, ChefWaitlistSubscription
from local_chefs.models import PostalCode, ChefPostalCode


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class PublicChefProfileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='chefuser', password='password', email='chef@example.com')
        UserRole.objects.create(user=self.user, is_chef=True)
        self.chef = Chef.objects.create(user=self.user, is_verified=True, background_checked=True, insured=True)

        self.postal = PostalCode.objects.create(code='10001', display_code='10001', country='US')
        ChefPostalCode.objects.create(chef=self.chef, postal_code=self.postal)

        self.public_photo = ChefPhoto.objects.create(
            chef=self.chef,
            image=self._image_file('public.jpg'),
            is_public=True,
            is_featured=True,
        )
        self.private_photo = ChefPhoto.objects.create(
            chef=self.chef,
            image=self._image_file('private.jpg'),
            is_public=False,
        )

    def _image_file(self, name):
        file_obj = BytesIO()
        Image.new('RGB', (1, 1)).save(file_obj, format='JPEG')
        file_obj.seek(0)
        return SimpleUploadedFile(name, file_obj.read(), content_type='image/jpeg')

    def test_public_profile_returns_public_photos_and_verification_flags(self):
        url = reverse('chefs:chef_public', args=[self.chef.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.chef.id)
        self.assertTrue(response.data['is_verified'])
        self.assertTrue(response.data['background_checked'])
        self.assertTrue(response.data['insured'])
        self.assertEqual(len(response.data['photos']), 1)
        self.assertEqual(response.data['photos'][0]['id'], self.public_photo.id)
        self.assertEqual(response.data['serving_postalcodes'][0]['postal_code'], '10001')

    def test_public_directory_filters_by_serving_area_and_paginate(self):
        other_user = CustomUser.objects.create_user(username='otherchef', password='password', email='other@example.com')
        UserRole.objects.create(user=other_user, is_chef=True)
        other_postal = PostalCode.objects.create(code='94110', display_code='94110', country='US')
        other_chef = Chef.objects.create(user=other_user, is_verified=True)
        ChefPostalCode.objects.create(chef=other_chef, postal_code=other_postal)

        PostalCode.objects.create(code='V6B1A1', display_code='V6B 1A1', country='CA')

        list_url = reverse('chefs:chef_public_directory')
        response = self.client.get(list_url, {'serves_postal': '10001', 'page_size': 1})

        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.chef.id)

        slug_url = reverse('chefs:chef_public_by_username', kwargs={'slug': self.user.username})
        slug_response = self.client.get(slug_url)
        self.assertEqual(slug_response.status_code, 200)
        self.assertEqual(slug_response.data['user']['username'], self.user.username)


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class WaitlistApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='waiter', password='password', email='waiter@example.com')
        self.chef_user = CustomUser.objects.create_user(username='chefwait', password='password', email='chefwait@example.com')
        UserRole.objects.create(user=self.chef_user, is_chef=True)
        self.chef = Chef.objects.create(user=self.chef_user, is_verified=True, is_on_break=True)

    def test_waitlist_subscribe_and_unsubscribe(self):
        status_url = reverse('chefs:waitlist_status', args=[self.chef.id])
        self.assertEqual(self.client.get(status_url).status_code, 200)

        self.client.force_authenticate(user=self.user)
        subscribe_url = reverse('chefs:waitlist_subscribe', args=[self.chef.id])
        subscribe_response = self.client.post(subscribe_url)
        self.assertEqual(subscribe_response.status_code, 200)
        self.assertTrue(ChefWaitlistSubscription.objects.filter(user=self.user, chef=self.chef, active=True).exists())

        status_response = self.client.get(status_url)
        self.assertTrue(status_response.data['subscribed'])

        unsubscribe_url = reverse('chefs:waitlist_unsubscribe', args=[self.chef.id])
        unsubscribe_response = self.client.delete(unsubscribe_url)
        self.assertEqual(unsubscribe_response.status_code, 204)
        self.assertFalse(ChefWaitlistSubscription.objects.filter(user=self.user, chef=self.chef, active=True).exists())

