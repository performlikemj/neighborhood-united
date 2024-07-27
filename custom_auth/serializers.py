from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address, CustomUser, UserRole
from local_chefs.models import PostalCode, ChefPostalCode
from django.utils.translation import gettext_lazy as _


class CustomUserSerializer(serializers.ModelSerializer):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=True,  # Allow for no allergies
    )

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'dietary_preference', 'custom_dietary_preference', 'allergies', 'custom_allergies', 'week_shift', 'email_confirmed', 'preferred_language', 'timezone']
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {},
            'email': {},
            'phone_number': {'required': False}  # Make phone_number not required
        }

    def __init__(self, *args, **kwargs):
        super(CustomUserSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and getattr(request, 'method', None) == 'POST':
            # Require username, email, and password only during registration (POST)
            self.fields['username'].required = True
            self.fields['username'].error_messages['required'] = _('Username is required.')
            self.fields['email'].required = True
            self.fields['email'].error_messages['required'] = _('Email is required.')
            self.fields['password'].required = True
            self.fields['password'].error_messages['required'] = _('Password is required.')
        else:
            # Not required during update operations
            self.fields['username'].required = False
            self.fields['email'].required = False
            self.fields['password'].required = False

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