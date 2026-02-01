# custom_auth/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Address, CustomUser, UserRole, HouseholdMember
from meals.models import CustomDietaryPreference
from local_chefs.models import PostalCode, ChefPostalCode
from meals.models import DietaryPreference
from django.utils.translation import gettext_lazy as _
from django_countries.fields import Country
from django_countries import countries
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class HouseholdMemberSerializer(serializers.ModelSerializer):
    dietary_preferences = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=DietaryPreference.objects.all(),
        required=False,
    )
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=True,
        required=False,
    )
    custom_allergies = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=True,
        required=False,
    )

    class Meta:
        model = HouseholdMember
        fields = ['id', 'name', 'age', 'dietary_preferences', 'allergies', 'custom_allergies', 'notes']

    def create(self, validated_data):
        prefs = validated_data.pop('dietary_preferences', [])
        member = HouseholdMember.objects.create(**validated_data)
        if prefs:
            member.dietary_preferences.set(prefs)
        return member

    def update(self, instance, validated_data):
        prefs = validated_data.pop('dietary_preferences', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if prefs is not None:
            instance.dietary_preferences.set(prefs)
        return instance
    
class CustomUserSerializer(serializers.ModelSerializer):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=True,  # Allow for no allergies
        required=False,
    )

    custom_allergies = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=True,
        required=False
    )
    
    # Handle dietary_preferences as ManyToManyField
    dietary_preferences = serializers.SlugRelatedField(
        many=True,
        slug_field='name',  # Using 'name' to represent dietary preferences
        queryset=DietaryPreference.objects.all(),
        required=False
    )
    
    # Handle custom_dietary_preferences as ManyToManyField
    custom_dietary_preferences = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=CustomDietaryPreference.objects.all(),
        required=False
    )
    
    # Add is_chef field from UserRole relationship
    is_chef = serializers.SerializerMethodField()
    is_email_verified = serializers.SerializerMethodField()
    current_role = serializers.SerializerMethodField()
    
    # Include address data directly in user response (avoids separate API call)
    address = serializers.SerializerMethodField()

    household_members = HouseholdMemberSerializer(many=True, required=False)
    
    class Meta:
        model = get_user_model()
        fields = [
            'id', 'username', 'email', 'unsubscribed_from_emails', 'password',
            'phone_number', 'dietary_preferences', 'custom_dietary_preferences',
            'allergies', 'custom_allergies', 'week_shift', 'email_confirmed', 'is_email_verified',
            'preferred_language', 'timezone', 'emergency_supply_goal', 'measurement_system',
            'personal_assistant_email', 'is_chef', 'current_role',
            'household_member_count', 'household_members',
            'auto_meal_plans_enabled',
            'address'  # Now included in user details response
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {},
            'email': {},
            'phone_number': {'required': False},  # Make phone_number not required
            'dietary_preferences': {'required': False},
            'allergies': {'required': False},
            'custom_dietary_preferences': {'required': False},  # Optional field
            'personal_assistant_email': {'read_only': True},  # Mark as read-only
            'auto_meal_plans_enabled': {'required': False},
        }

    def get_is_chef(self, obj):
        """
        Get the is_chef status from the related UserRole model.
        Returns False if UserRole doesn't exist for the user.
        """
        try:
            user_role = UserRole.objects.get(user=obj)
            return user_role.is_chef
        except UserRole.DoesNotExist:
            return False

    def get_current_role(self, obj):
        """
        Get the current_role from the related UserRole model.
        Returns 'customer' if UserRole doesn't exist for the user.
        """
        try:
            user_role = UserRole.objects.get(user=obj)
            return user_role.current_role
        except UserRole.DoesNotExist:
            return 'customer'

    def get_is_email_verified(self, obj):
        if hasattr(obj, 'is_email_verified'):
            return bool(obj.is_email_verified)
        return bool(getattr(obj, 'email_confirmed', False))

    def get_address(self, obj):
        """
        Get user's address data inline, avoiding need for separate API call.
        Returns None if user has no address.
        """
        try:
            address = obj.address
            if not address:
                return None
            return {
                'id': address.id,
                'street': address.street,
                'city': address.city,
                'state': address.state,
                'input_postalcode': address.input_postalcode,
                'postalcode': address.input_postalcode,  # Alias for frontend compatibility
                'postal_code': address.input_postalcode,  # Another common alias
                'normalized_postalcode': address.normalized_postalcode,
                'original_postalcode': address.original_postalcode,
                'country': str(address.country) if address.country else None,
            }
        except Address.DoesNotExist:
            return None

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
        custom_dietary_prefs = validated_data.pop('custom_dietary_preferences', [])
        household_members_data = validated_data.pop('household_members', [])
        # Ensure household size defaults to 1 unless user adds members
        requested_household_count = validated_data.get('household_member_count', 1)
        if not requested_household_count or requested_household_count < 1:
            requested_household_count = 1
        if household_members_data:
            requested_household_count = len(household_members_data)
        user = get_user_model()( 
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            phone_number=validated_data.get('phone_number', ''),
            preferred_language=validated_data.get('preferred_language', 'en'),
            timezone=validated_data.get('timezone', 'UTC'),
            allergies=validated_data.get('allergies', []),
            custom_allergies=validated_data.get('custom_allergies', []),
            emergency_supply_goal=validated_data.get('emergency_supply_goal', 0), 
            measurement_system=validated_data.get('measurement_system', 'METRIC'),
            household_member_count=requested_household_count,
            auto_meal_plans_enabled=validated_data.get('auto_meal_plans_enabled', True),
        )
        user.set_password(validated_data['password'])
        user.save()
        user.dietary_preferences.set(validated_data.get('dietary_preferences', []))
        user.custom_dietary_preferences.set(custom_dietary_prefs)
        # Create household members if provided
        if household_members_data:
            for member_data in household_members_data:
                member_serializer = HouseholdMemberSerializer(data=member_data)
                if member_serializer.is_valid():
                    member_serializer.save(user=user)
                else:
                    raise ValidationError({
                        'household_members': member_serializer.errors
                    })
        return user


    def update(self, instance, validated_data):
        custom_dietary_prefs = validated_data.pop('custom_dietary_preferences', None)
        household_members_data = validated_data.pop('household_members', None)
        
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            elif attr == 'dietary_preferences':
                instance.dietary_preferences.set(value)  # Update ManyToMany field
            elif attr == 'allergies':
                instance.allergies = value
            elif attr == 'household_member_count':
                if value < 1:
                    raise ValidationError("Household member count must be greater than 0.")
                setattr(instance, attr, value)
            elif attr == 'custom_allergies':
                instance.custom_allergies = value
            else:
                setattr(instance, attr, value)
        
        if custom_dietary_prefs is not None:
            instance.custom_dietary_preferences.set(custom_dietary_prefs)
            
        # Handle household members if provided
        if household_members_data is not None:
            # Clear existing household members
            instance.household_members.all().delete()
            
            # Create new household members using the serializer
            for member_data in household_members_data:
                member_serializer = HouseholdMemberSerializer(data=member_data)
                if member_serializer.is_valid():
                    member_serializer.save(user=instance)
                else:
                    raise ValidationError(f"Invalid household member data: {member_serializer.errors}")
                    
        instance.save()
        return instance

    def validate_allergies(self, value):
        """Coerce empty or null inputs to an empty list for ArrayField compatibility."""
        if value is None or value == '' or value == []:
            return []
        return value

    def validate_custom_allergies(self, value):
        """Coerce empty or null inputs to an empty list for ArrayField compatibility."""
        if value is None or value == '' or value == []:
            return []
        return value

class AddressSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), write_only=True, required=False)
    street = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    input_postalcode = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # Accept postal_code as an alias for input_postalcode (frontend compatibility)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Address
        fields = ['id', 'user', 'street', 'city', 'state', 'input_postalcode', 'postal_code', 'country']

    def validate(self, data):
        # Handle postal_code alias - copy to input_postalcode if provided
        if 'postal_code' in data and data['postal_code']:
            data['input_postalcode'] = data.pop('postal_code')
        elif 'postal_code' in data:
            data.pop('postal_code')
        return data

    def to_representation(self, instance):
        """
        Convert the country code back to the country name for output.
        Also include postal_code alias for frontend compatibility.
        """
        representation = super().to_representation(instance)
        country_code = representation.get('country')
        if country_code:
            # Replace the country code with the full name
            country_name = dict(countries).get(country_code, country_code)
            representation['country'] = country_name
        # Add postal_code alias
        representation['postal_code'] = representation.get('input_postalcode')
        return representation

    def create(self, validated_data):
        user = validated_data.get('user')
        if user and Address.objects.filter(user=user).exists():
            raise serializers.ValidationError("An address for this user already exists.")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.street = validated_data.get('street', instance.street)
        instance.city = validated_data.get('city', instance.city)
        instance.state = validated_data.get('state', instance.state)
        instance.input_postalcode = validated_data.get('input_postalcode', instance.input_postalcode)

        # Use the validated country code, not the full name
        instance.country = validated_data.get('country', instance.country)  # This will now be the code 'JP'
        
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

class OnboardingUserSerializer(serializers.ModelSerializer):
    """
    Streamlined serializer for onboarding process.
    Only requires essential fields and provides sensible defaults.
    """
    household_members = HouseholdMemberSerializer(many=True, required=False)
    
    # Handle dietary_preferences as ManyToManyField
    dietary_preferences = serializers.SlugRelatedField(
        many=True,
        slug_field='name',  # Using 'name' to represent dietary preferences
        queryset=DietaryPreference.objects.all(),
        required=False
    )
    
    # Handle custom_dietary_preferences as ManyToManyField
    custom_dietary_preferences = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=CustomDietaryPreference.objects.all(),
        required=False
    )
    
    class Meta:
        model = get_user_model()
        fields = [
            'id', 'username', 'email', 'password',
            'phone_number', 'preferred_language', 'timezone',
            'dietary_preferences', 'custom_dietary_preferences',
            'allergies', 'custom_allergies',
            'emergency_supply_goal', 'measurement_system', 'household_member_count', 'household_members',
            'auto_meal_plans_enabled'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {'required': True},
            'email': {'required': True},
            'phone_number': {'required': False},
            'preferred_language': {'required': False},
            'timezone': {'required': False},
            'dietary_preferences': {'required': False},
            'custom_dietary_preferences': {'required': False},
            'allergies': {'required': False},
            'custom_allergies': {'required': False},
            'emergency_supply_goal': {'required': False},
            'measurement_system': {'required': False},
            'household_member_count': {'required': False},
            'auto_meal_plans_enabled': {'required': False},
        }
    
    def create(self, validated_data):
        """Create user with sensible defaults for optional fields."""
        # Remove nested fields
        household_members_data = validated_data.pop('household_members', [])
        dietary_preferences_data = validated_data.pop('dietary_preferences', [])
        custom_dietary_preferences_data = validated_data.pop('custom_dietary_preferences', [])
        
        # Set defaults for optional fields
        defaults = {
            'phone_number': '',
            'preferred_language': 'en',
            'timezone': 'America/New_York',
            'allergies': [],
            'custom_allergies': [],
            'emergency_supply_goal': 7,
            'measurement_system': 'METRIC',
            'household_member_count': 1,
            'is_active': True,
        }
        
        # Apply defaults for missing fields
        for field, default_value in defaults.items():
            if field not in validated_data:
                validated_data[field] = default_value
        
        # Create user using Django's create_user method
        user = get_user_model().objects.create_user(**validated_data)
        
        # Set ManyToMany relationships
        if dietary_preferences_data:
            user.dietary_preferences.set(dietary_preferences_data)
        if custom_dietary_preferences_data:
            user.custom_dietary_preferences.set(custom_dietary_preferences_data)
        
        # Create household members if provided
        if household_members_data:
            for member_data in household_members_data:
                member_data['user'] = user
                HouseholdMember.objects.create(**member_data)
        
        return user
