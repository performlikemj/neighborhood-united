# chefs/serializers.py
from rest_framework import serializers
from .models import Chef
from custom_auth.serializers import CustomUserSerializer
from local_chefs.serializers import PostalCodeSerializer, ChefRequestSerializer

from custom_auth.serializers import CustomUserSerializer  # Assuming this is the correct import path

class ChefSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Include the user serializer
    serving_postalcodes = PostalCodeSerializer(many=True, read_only=True)
    chef_request = ChefRequestSerializer(read_only=True)  # Assuming you want to include pending requests

    class Meta:
        model = Chef
        fields = ['user', 'experience', 'bio', 'serving_postalcodes', 'profile_pic', 'review_summary', 'chef_embedding', 'chef_request']
