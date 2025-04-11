# Description: This file contains the models for the local_chefs app.
from django.db import models
from django_countries.fields import CountryField
import re

class PostalCode(models.Model):
    code = models.CharField(max_length=15)  # Normalized format (uppercase, no special chars)
    display_code = models.CharField(max_length=20, blank=True, null=True)  # Original format for display
    country = CountryField(default='US')  # Default to US, but can be changed

    class Meta:
        unique_together = ('code', 'country')  # Ensure uniqueness per country

    def __str__(self):
        display = self.display_code or self.code
        return f"{display}, {self.country.name}"

    @staticmethod
    def normalize_code(postal_code):
        """
        Normalize a postal code for storage and lookup.
        Removes all non-alphanumeric characters and converts to uppercase.
        """
        if not postal_code:
            return None
            
        return re.sub(r'[^A-Z0-9]', '', postal_code.upper())
    
    @classmethod
    def get_or_create_normalized(cls, code, country):
        """
        Get or create a PostalCode with normalized code while preserving the original format.
        
        Args:
            code (str): The postal code (can be in any format)
            country: The country code or object
            
        Returns:
            tuple: (postal_code, created) - The PostalCode object and whether it was created
        """
        if not code or not country:
            return None, False
            
        # Store the original format for display
        original_code = code
        
        # Normalize for database storage and lookups
        normalized_code = cls.normalize_code(code)
        
        postal_code, created = cls.objects.get_or_create(
            code=normalized_code,
            country=country,
            defaults={'display_code': original_code}
        )
        
        # If not created but display_code is not set, update it
        if not created and not postal_code.display_code:
            postal_code.display_code = original_code
            postal_code.save(update_fields=['display_code'])
            
        return postal_code, created
    
    def is_served_by_any_chef(self):
        """Check if any chef serves this postal code"""
        return self.chefpostalcode_set.exists()


class ChefPostalCode(models.Model):
    chef = models.ForeignKey('chefs.Chef', on_delete=models.CASCADE)
    postal_code = models.ForeignKey(PostalCode, on_delete=models.CASCADE, related_name='chefpostalcode_set')

    class Meta:
        unique_together = ('chef', 'postal_code')

    def __str__(self):
        return f"{self.chef.user.username} - {self.postal_code}"
        
    @classmethod
    def add_postal_code_for_chef(cls, chef, postal_code, country):
        """
        Add a postal code to a chef's service area, normalizing the code first.
        
        Args:
            chef: Chef object
            postal_code: Postal code string (will be normalized)
            country: Country code or object
            
        Returns:
            ChefPostalCode: The created or existing relationship
        """
        postal_code_obj, _ = PostalCode.get_or_create_normalized(postal_code, country)
        
        if not postal_code_obj:
            return None
            
        chef_postal_code, created = cls.objects.get_or_create(
            chef=chef,
            postal_code=postal_code_obj
        )
        
        return chef_postal_code