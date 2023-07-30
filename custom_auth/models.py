from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField


# Create your models here.
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('chef', 'Chef'),
        ('customer', 'Customer'),
    ]
    current_role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    email_confirmed = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20)
    preferences = models.TextField(blank=True)
    is_chef = models.BooleanField(default=False)  # Add this line to keep track of whether user is/was a chef
    new_email = models.EmailField(blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    initial_email_confirmed = models.BooleanField(default=False)


class Address(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    address_type = models.CharField(max_length=10, choices=[('home', 'Home'), ('business', 'Business')])
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    zipcode = models.CharField(max_length=10)
    country = CountryField()

    def __str__(self):
        return f'{self.street}, {self.city}, {self.state} {self.zipcode}, {self.country}'