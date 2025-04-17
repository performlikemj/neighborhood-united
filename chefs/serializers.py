# chefs/serializers.py
from rest_framework import serializers
from .models import Chef
from local_chefs.models import PostalCode  # Added import for PostalCode model
from custom_auth.serializers import CustomUserSerializer
from local_chefs.serializers import ChefRequestSerializer # Removed PostalCodeSerializer from this import

from custom_auth.serializers import CustomUserSerializer  # Assuming this is the correct import path

# Added PostalCodeSerializer class definition
class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = ['code']

class ChefSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Include the user serializer
    serving_postalcodes = PostalCodeSerializer(many=True, read_only=True)
    chef_request = ChefRequestSerializer(read_only=True)  # Assuming you want to include pending requests

    class Meta:
        model = Chef
        fields = ['user', 'experience', 'bio', 'serving_postalcodes', 'profile_pic', 'review_summary', 'chef_embedding', 'chef_request']
