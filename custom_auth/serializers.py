from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address, CustomUser, UserRole
from local_chefs.models import PostalCode, ChefPostalCode
from django.utils.translation import gettext_lazy as _
from django_countries.fields import Country
from django_countries import countries

class CustomUserSerializer(serializers.ModelSerializer):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=True,  # Allow for no allergies
    )

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'dietary_preference', 'custom_dietary_preference', 'allergies', 'custom_allergies', 'week_shift', 'email_confirmed', 'preferred_language', 'timezone']
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
            if attr in ['username', 'email', 'phone_number', 'dietary_preference', 'custom_dietary_preference', 'allergies', 'custom_allergies', 'password', 'preferred_language', 'timezone']:
                if attr == 'password':
                    instance.set_password(value)
                else:
                    setattr(instance, attr, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        country_code = representation.get('country')
        # Replace the country code with the full name
        if country_code:
            country_name = dict(countries).get(country_code, country_code)
            representation['country'] = country_name
        return representation
    
    def validate_country(self, value):
        # Convert the full country name back to the two-letter country code
        if value:
            country_dict = {name: code for code, name in dict(countries).items()}
            country_code = country_dict.get(value)
            if not country_code:
                raise serializers.ValidationError(f"Invalid country name: {value}")
            return country_code
        return value
    
class AddressSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True
    )
    street = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    input_postalcode = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Address
        fields = ['user', 'street', 'city', 'state', 'input_postalcode', 'country']


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