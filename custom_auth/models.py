# custom_auth/models.py

from django.db import models
from django.utils import timezone
from datetime import timezone as py_tz
from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField
from local_chefs.models import PostalCode, ChefPostalCode
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.conf.locale import LANG_INFO
import uuid

# Create your models here.
class CustomUser(AbstractUser):
    MEASUREMENT_CHOICES = [
        ('US', 'US Customary'),
        ('METRIC', 'Metric'),
    ]
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

    # Get language choices from Django's built-in language info
    @staticmethod
    def get_language_choices():
        """
        Returns a list of tuples (language_code, language_name) for all languages
        supported by Django, sorted by language name.
        """
        # Filter out languages without a name or name_local for stability
        choices = [(code, info['name']) for code, info in LANG_INFO.items() 
                  if 'name' in info and 'name_local' in info]
        return sorted(choices, key=lambda x: x[1])  # Sort by language name

    email = models.EmailField(unique=True, blank=False, null=False)
    email_confirmed = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    new_email = models.EmailField(blank=True, null=True)
    token_created_at = models.DateTimeField(blank=True, null=True)
    initial_email_confirmed = models.BooleanField(default=False)
    # Field to store week_shift for context when chatting with assistant
    week_shift = models.IntegerField(default=0)
    email_token = models.UUIDField(editable=False, unique=True, db_index=True)
    # Measurement system preference (default Metric; US users can switch or be defaulted during onboarding)
    measurement_system = models.CharField(
        max_length=10,
        choices=MEASUREMENT_CHOICES,
        default='METRIC'
    )
    dietary_preferences = models.ManyToManyField(
        'meals.DietaryPreference',  # Use the app name and model name as a string
        blank=True,
        related_name='users'
    )
    custom_dietary_preferences = models.ManyToManyField(
        'meals.CustomDietaryPreference',
        blank=True,
        related_name='users'
    )
    preferred_language = models.CharField(max_length=10, default='en')  # Increased max_length to accommodate longer language codes
    allergies = ArrayField(
        models.CharField(max_length=20, choices=ALLERGY_CHOICES),
        default=list,
        blank=True,
    )
    custom_allergies = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
    )
    timezone = models.CharField(max_length=100, default='UTC')
    # Email preference field
    unsubscribed_from_emails = models.BooleanField(default=False)
    emergency_supply_goal = models.PositiveIntegerField(default=0)  # Number of days of supplies the user wants
    # Number of household members (replaces preferred_servings)
    household_member_count = models.PositiveIntegerField(
        default=1,
        help_text="Total number of people in the user's household."
    )
    # Controls whether the system auto-generates weekly meal plans for the user
    auto_meal_plans_enabled = models.BooleanField(
        default=True,
        help_text="If False, do not auto-generate weekly meal plans."
    )
    
    @property
    def personal_assistant_email(self):
        if self.email_token:
            return f"mj+{self.email_token}@sautai.com"
        return None

    @property
    def is_email_verified(self):
        """Convenience alias used by public APIs/badges."""
        return bool(getattr(self, 'email_confirmed', False))

    def save(self, *args, **kwargs):
        self.username = self.username.lower()
        # Ensure timezone-aware datetimes for fields when USE_TZ is enabled
        try:
            if getattr(self, 'date_joined', None) and timezone.is_naive(self.date_joined):
                try:
                    self.date_joined = timezone.make_aware(self.date_joined, timezone.get_current_timezone())
                except Exception:
                    self.date_joined = self.date_joined.replace(tzinfo=py_tz.utc)
            if getattr(self, 'last_login', None) and timezone.is_naive(self.last_login):
                try:
                    self.last_login = timezone.make_aware(self.last_login, timezone.get_current_timezone())
                except Exception:
                    self.last_login = self.last_login.replace(tzinfo=py_tz.utc)
            if getattr(self, 'token_created_at', None) and timezone.is_naive(self.token_created_at):
                try:
                    self.token_created_at = timezone.make_aware(self.token_created_at, timezone.get_current_timezone())
                except Exception:
                    self.token_created_at = self.token_created_at.replace(tzinfo=py_tz.utc)
        except Exception:
            pass
        if not self.pk and not self.email_token:  # If creating a new user and token isn't set
            self.email_token = uuid.uuid4()
        super().save(*args, **kwargs)

class Address(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='address')
    street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    input_postalcode = models.CharField(max_length=10, blank=True, null=True)  # Normalized format for lookups
    display_postalcode = models.CharField(max_length=15, blank=True, null=True)  # Original user input format
    latitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    country = CountryField(blank=True, null=True)

    def __str__(self):
        display_code = self.display_postalcode or self.input_postalcode
        return f'{self.user} - {display_code}, {self.country}'

    def normalize_postal_code(self, postal_code):
        """
        Normalize the postal code for database storage and lookups
        Removes all non-alphanumeric characters and converts to uppercase
        """
        if not postal_code:
            return None
            
        import re
        # Remove all non-alphanumeric characters and convert to uppercase
        return re.sub(r'[^A-Z0-9]', '', postal_code.upper())

    def clean(self):
        # Store the original user input for display
        if self.input_postalcode and not self.display_postalcode:
            self.display_postalcode = self.input_postalcode
            
        # Normalize postal code for lookups
        if self.input_postalcode and self.country:
            # Store the original format before normalizing
            if not self.display_postalcode:
                self.display_postalcode = self.input_postalcode
                
            # Normalize for database storage and lookups
            self.input_postalcode = self.normalize_postal_code(self.input_postalcode)
            
            # You could add country-specific postal code validation here
            # For example, US postal codes are 5 digits or 5+4 digits
            if self.country == 'US' and not (
                len(self.input_postalcode) == 5 or len(self.input_postalcode) == 9
            ):
                raise ValidationError({'input_postalcode': 'US postal codes must be 5 digits or 9 digits (ZIP+4)'})
            
            # Canadian postal codes are in the format A1A1A1 (after normalization)
            elif self.country == 'CA' and not (
                len(self.input_postalcode) == 6 and
                self.input_postalcode[0::2].isalpha() and
                self.input_postalcode[1::2].isdigit()
            ):
                raise ValidationError({'input_postalcode': 'Canadian postal codes must be in the format A1A 1A1'})
                
            # Japanese postal codes are 7 digits after normalization
            elif self.country == 'JP' and not (
                len(self.input_postalcode) == 7 and self.input_postalcode.isdigit()
            ):
                raise ValidationError({'input_postalcode': 'Japanese postal codes must be 7 digits'})
                
        # Require both country and postal code if either is provided
        if (self.country and not self.input_postalcode) or (self.input_postalcode and not self.country):
            raise ValidationError('Both country and postal code must be provided together')

    def get_or_create_postal_code(self):
        """
        Gets the corresponding PostalCode object for this address, creating one if it doesn't exist.
        Returns None if either country or input_postalcode is missing.
        """
        if not self.country or not self.input_postalcode:
            return None
            
        postal_code, created = PostalCode.objects.get_or_create(
            code=self.input_postalcode,  # Using normalized code
            country=self.country
        )
        return postal_code

    def is_postalcode_served(self):
        """
        Checks if the input postal code is in the list of served postal codes.
        Returns True if served, False otherwise.
        """
        # First ensure the postal code exists in our system
        try:
            postal_code = PostalCode.objects.get(
                code=self.input_postalcode,  # Using normalized code
                country=self.country
            )
            # Then check if any chef is serving this postal code
            return ChefPostalCode.objects.filter(postal_code=postal_code).exists()
        except PostalCode.DoesNotExist:
            return False

    def save(self, *args, **kwargs):
        # Check if this is an update and if postal code has changed
        should_run_full_clean = True
        if self.pk:  # Existing instance
            try:
                original = Address.objects.get(pk=self.pk)
                # Normalize the current input postal code for accurate comparison
                current_normalized_postalcode = self.normalize_postal_code(self.input_postalcode)
                if original.input_postalcode != current_normalized_postalcode:
                    self.latitude = None
                    self.longitude = None

                # Only run full_clean if either country or input_postalcode changed
                original_country = original.country
                original_postal = original.input_postalcode
                new_country = self.country
                new_postal = current_normalized_postalcode
                should_run_full_clean = (original_country != new_country) or (original_postal != new_postal)
            except Address.DoesNotExist:
                # If somehow not found, treat as new and validate
                should_run_full_clean = True
        else:
            # New instance – validate
            should_run_full_clean = True

        if should_run_full_clean:
            self.full_clean()  # Validate only when relevant fields changed or on create

        super().save(*args, **kwargs)



class HouseholdMember(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='household_members')
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(blank=True, null=True)
    dietary_preferences = models.ManyToManyField(
        'meals.DietaryPreference',
        blank=True,
        related_name='household_members'
    )
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


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


class OnboardingSession(models.Model):
    """Track registration info collected for guest onboarding."""

    guest_id = models.CharField(max_length=40, unique=True)
    data = models.JSONField(default=dict)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OnboardingSession({self.guest_id})"
    
