import tempfile
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image

from custom_auth.models import CustomUser, UserRole
from chefs.models import Chef, ChefPhoto


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ChefPhotoUploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='chefupload', password='password')
        UserRole.objects.create(user=self.user, is_chef=True, current_role='chef')
        self.chef = Chef.objects.create(user=self.user, is_verified=True)

    def _image_file(self, name):
        file_obj = BytesIO()
        Image.new('RGB', (1, 1)).save(file_obj, format='JPEG')
        file_obj.seek(0)
        return SimpleUploadedFile(name, file_obj.read(), content_type='image/jpeg')

    def test_upload_photo_defaults_to_public(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('chefs:me_upload_photo')
        response = self.client.post(
            url,
            data={
                'image': self._image_file('upload.jpg'),
                'title': 'E2E Photo Title',
                'caption': 'E2E Caption',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        photo = ChefPhoto.objects.get(chef=self.chef, title='E2E Photo Title')
        self.assertTrue(photo.is_public)

        profile_url = reverse('chefs:me_chef_profile')
        profile_response = self.client.get(profile_url)
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.data['photos'][0]['id'], photo.id)
