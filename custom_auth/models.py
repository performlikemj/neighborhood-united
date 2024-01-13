from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField


# Create your models here.
class CustomUser(AbstractUser):
    DIETARY_CHOICES = [
    ('Vegan', 'Vegan'),
    ('Vegetarian', 'Vegetarian'),
    ('Pescatarian', 'Pescatarian'),
    ('Gluten-Free', 'Gluten-Free'),
    ('Keto', 'Keto'),
    ('Paleo', 'Paleo'),
    ('Halal', 'Halal'),
    ('Kosher', 'Kosher'),
    ('Low-Calorie', 'Low-Calorie'),
    ('Low-Sodium', 'Low-Sodium'),
    ('High-Protein', 'High-Protein'),
    ('Dairy-Free', 'Dairy-Free'),
    ('Nut-Free', 'Nut-Free'),
    ('Raw Food', 'Raw Food'),
    ('Whole 30', 'Whole 30'),
    ('Low-FODMAP', 'Low-FODMAP'),
    ('Diabetic-Friendly', 'Diabetic-Friendly'),
    ('Everything', 'Everything'),
    # ... add more as needed
    ]

    email_confirmed = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20)
    new_email = models.EmailField(blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    initial_email_confirmed = models.BooleanField(default=False)
    # Field to store week_shift for context when chatting with assistant
    week_shift = models.IntegerField(default=0)
    dietary_preference = models.CharField(max_length=20, choices=DIETARY_CHOICES, default='Everything')

class Address(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    postalcode = models.ForeignKey('local_chefs.PostalCode', on_delete=models.SET_NULL, null=True, blank=True)
    country = CountryField()

    def __str__(self):
        return f'{self.user} - {self.postalcode}, {self.country}'


class UserRole(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_chef = models.BooleanField(default=False)
    current_role = models.CharField(max_length=10, choices=[('chef', 'Chef'), ('customer', 'Customer')], default='customer')
    
    def switch_to_chef(self):
        self.is_chef = True
        self.current_role = 'chef'
        self.save()

    # more methods for role management
    def switch_to_customer(self):
        self.is_chef = False
        self.current_role = 'customer'
        self.save()

    def __str__(self):
        return f'{self.user.username} - {self.current_role}'
    


