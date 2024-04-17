from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address, CustomUser, UserRole
from local_chefs.models import PostalCode, ChefPostalCode


class CustomUserSerializer(serializers.ModelSerializer):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=True,  # Allow for no allergies
    )

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'dietary_preference', 'allergies', 'week_shift', 'email_confirmed']
        extra_kwargs = {'password': {'write_only': True, 'required': False}, 'username': {'required': False}, 'email': {'required': False}}

    def create(self, validated_data):
        user = get_user_model()(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number'),
            dietary_preference=validated_data.get('dietary_preference'),
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)
        instance.dietary_preference = validated_data.get('dietary_preference', instance.dietary_preference)
        
        # Handle allergies; ensure it doesn't override with None if not provided
        if 'allergies' in validated_data:
            instance.allergies = validated_data['allergies']
        
        # Optional: Handle password updates, if included
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])

        instance.save()
        return instance

class AddressSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True
    )

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