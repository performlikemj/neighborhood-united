# custom_auth/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address, CustomUser, UserRole
from local_chefs.models import PostalCode, ChefPostalCode
from django.utils.translation import gettext_lazy as _
from django_countries.fields import Country
from django_countries import countries
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class CustomUserSerializer(serializers.ModelSerializer):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=True,  # Allow for no allergies
    )

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'email_daily_instructions', 'email_meal_plan_saved', 'email_instruction_generation', 'password', 'phone_number', 'dietary_preference', 'custom_dietary_preference', 'allergies', 'custom_allergies', 'week_shift', 'email_confirmed', 'preferred_language', 'timezone']
        extra_kwargs = {'password': {'write_only': True, 'required': False}, 'username': {'required': False}, 'email': {'required': False}, 'phone_number': {'required': False}}

    def create(self, validated_data):
        user = get_user_model()(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number', ''), 
            dietary_preference=validated_data.get('dietary_preference'),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr in ['username', 'email', 'email_daily_instructions', 'email_meal_plan_saved', 'email_instruction_generation', 'phone_number', 'dietary_preference', 'custom_dietary_preference', 'allergies', 'custom_allergies', 'password', 'preferred_language', 'timezone']:
                if attr == 'password':
                    instance.set_password(value)
                else:
                    setattr(instance, attr, value)
        instance.save()
        return instance
    
class AddressSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True)
    street = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    input_postalcode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)


    class Meta:
        model = Address
        fields = ['user', 'street', 'city', 'state', 'input_postalcode', 'country']

    # def validate_country(self, value):
    #     # Directly validate against the model's CountryField
    #     try:
    #         address = Address(country=value)
    #         address.full_clean()  # Trigger full validation, including country code validation
    #     except ValidationError as e:
    #         raise serializers.ValidationError(f"Invalid country code: {value}")
    #     return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        country_code = representation.get('country')
        # Replace the country code with the full name
        if country_code:
            country_name = dict(countries).get(country_code, country_code)
            representation['country'] = country_name
        return representation
    
    def create(self, validated_data):
        user = validated_data.get('user')
        # Check if an address already exists for this user
        if Address.objects.filter(user=user).exists():
            raise serializers.ValidationError("An address for this user already exists.")
        
        # If no address exists, create a new one
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Update the existing address instance with new data
        instance.street = validated_data.get('street', instance.street)
        instance.city = validated_data.get('city', instance.city)
        instance.state = validated_data.get('state', instance.state)
        instance.input_postalcode = validated_data.get('input_postalcode', instance.input_postalcode)
        instance.country = validated_data.get('country', instance.country)
        instance.save()
        return instance

class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = ['code']

    def create(self, validated_data):
        # Create or update the PostalCode instance
        postal_code, created = PostalCode.objects.get_or_create(**validated_data)
        return postal_code


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'is_chef', 'current_role']

    def update(self, instance, validated_data):
        # Update the UserRole instance
        instance.current_role = validated_data.get('current_role', instance.current_role)
        instance.is_chef = validated_data.get('is_chef', instance.is_chef)
        instance.save()
        return instance