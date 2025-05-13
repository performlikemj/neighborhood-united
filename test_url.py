from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

try:
    url = reverse('custom_auth:register')
    print(f"Register URL resolves correctly: {url}")
except NoReverseMatch as e:
    print(f"Error resolving URL: {e}")

try:
    url = reverse('custom_auth:register_api')
    print(f"Register API URL resolves correctly: {url}")
except NoReverseMatch as e:
    print(f"Error resolving URL: {e}") 