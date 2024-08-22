# local_chefs/serializers.py
from rest_framework import serializers
from .models import PostalCode, ChefPostalCode
from chefs.serializers import ChefSerializer

class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = ['code']

class ChefPostalCodeSerializer(serializers.ModelSerializer):
    chef = ChefSerializer(read_only=True)  # Serializes the related Chef instance
    postal_code = PostalCodeSerializer(read_only=True)  # Serializes the related PostalCode instance

    class Meta:
        model = ChefPostalCode
        fields = ['chef', 'postal_code']