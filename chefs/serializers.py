# chefs/serializers.py
from rest_framework import serializers
from .models import ChefRequest # Import ChefRequest model
# Removed PostalCode import as PostalCodeSerializer is moved
from custom_auth.serializers import CustomUserSerializer
# Import Base Serializer if needed - not currently needed for ChefRequestSerializer
# from .base_serializers import ChefSerializer

# Define the new ChefRequestSerializer
class ChefRequestSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True) # Include user details

    class Meta:
        model = ChefRequest
        # Include relevant fields from the ChefRequest model
        fields = ['id', 'user', 'experience', 'bio', 'profile_pic', 'is_approved', 'created_at', 'updated_at'] # Added missing fields
        read_only_fields = ['id', 'user', 'is_approved', 'created_at', 'updated_at'] # Assuming these shouldn't be directly writable here

# Removed PostalCodeSerializer class definition

# Removed ChefSerializer class definition
