from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField
from local_chefs.models import PostalCode
from django.contrib.postgres.fields import ArrayField

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

    ALLERGY_CHOICES = [
    ('Peanuts', 'Peanuts'),
    ('Tree nuts', 'Tree nuts'),  # Includes almonds, cashews, walnuts, etc.
    ('Milk', 'Milk'),  # Refers to dairy allergy
    ('Egg', 'Egg'),
    ('Wheat', 'Wheat'),  # Common in gluten intolerance
    ('Soy', 'Soy'),
    ('Fish', 'Fish'),  # Includes allergies to specific types of fish
    ('Shellfish', 'Shellfish'),  # Includes shrimp, crab, lobster, etc.
    ('Sesame', 'Sesame'),
    ('Mustard', 'Mustard'),
    ('Celery', 'Celery'),
    ('Lupin', 'Lupin'),  # Common in Europe, refers to Lupin beans and seeds
    ('Sulfites', 'Sulfites'),  # Often found in dried fruits and wine
    ('Molluscs', 'Molluscs'),  # Includes snails, slugs, mussels, oysters, etc.
    ('Corn', 'Corn'),
    ('Gluten', 'Gluten'),  # For broader gluten-related allergies beyond wheat
    ('Kiwi', 'Kiwi'),
    ('Latex', 'Latex'),  # Latex-fruit syndrome related allergies
    ('Pine Nuts', 'Pine Nuts'),
    ('Sunflower Seeds', 'Sunflower Seeds'),
    ('Poppy Seeds', 'Poppy Seeds'),
    ('Fennel', 'Fennel'),
    ('Peach', 'Peach'),
    ('Banana', 'Banana'),
    ('Avocado', 'Avocado'),
    ('Chocolate', 'Chocolate'),
    ('Coffee', 'Coffee'),
    ('Cinnamon', 'Cinnamon'),
    ('Garlic', 'Garlic'),
    ('Chickpeas', 'Chickpeas'),
    ('Lentils', 'Lentils'),
    ('None', 'None'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ja', 'Japanese'),
        ('es', 'Spanish'),
        ('fr', 'French'),
    ]

    email = models.EmailField(unique=True, blank=False, null=False)
    email_confirmed = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    new_email = models.EmailField(blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    initial_email_confirmed = models.BooleanField(default=False)
    # Field to store week_shift for context when chatting with assistant
    week_shift = models.IntegerField(default=0)
    dietary_preference = models.CharField(max_length=20, choices=DIETARY_CHOICES, default='Everything', blank=True, null=True)
    custom_dietary_preference = models.CharField(max_length=200, blank=True, null=True)
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')
    allergies = ArrayField(
        models.CharField(max_length=20, choices=ALLERGY_CHOICES),
        default=list,
        blank=True,
    )
    custom_allergies = models.CharField(max_length=200, blank=True, null=True)
    timezone = models.CharField(max_length=100, default='UTC')


    def save(self, *args, **kwargs):
        self.username = self.username.lower()
        super().save(*args, **kwargs)

class Address(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='address')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=255)
    input_postalcode = models.CharField(max_length=10, blank=True, null=True)  # User input postal code
    country = CountryField()

    def __str__(self):
        return f'{self.user} - {self.input_postalcode}, {self.country}'

    def is_postalcode_served(self):
        """
        Checks if the input postal code is in the list of served postal codes.
        Returns True if served, False otherwise.
        """
        return PostalCode.objects.filter(code=self.input_postalcode).exists()

class UserRole(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_chef = models.BooleanField(default=False)
    current_role = models.CharField(max_length=10, choices=[('chef', 'Chef'), ('customer', 'Customer')], default='customer')
    
    def switch_to_chef(self):
        self.current_role = 'chef'
        self.save()

    # more methods for role management
    def switch_to_customer(self):
        self.current_role = 'customer'
        self.save()

    def __str__(self):
        return f'{self.user.username} - {self.current_role}'
    


