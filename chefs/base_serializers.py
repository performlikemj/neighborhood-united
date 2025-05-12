from rest_framework import serializers
from .models import Chef, ChefRequest
from local_chefs.models import PostalCode
from custom_auth.serializers import CustomUserSerializer

class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = ['code']

class ChefSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Include the user serializer
    serving_postalcodes = PostalCodeSerializer(many=True, read_only=True)
    # Use the ChefRequestSerializer defined elsewhere, sourcing it from the related user
    # Note: We might need to adjust ChefRequestSerializer import if it causes issues later
    chef_request = serializers.PrimaryKeyRelatedField(read_only=True, source='user.chefrequest') # Simplified for now

    class Meta:
        model = Chef
        fields = ['id', 'user', 'experience', 'bio', 'serving_postalcodes', 'profile_pic', 'review_summary', 'chef_embedding', 'chef_request', 'is_active', 'service_radius', 'cuisine_types'] # Added missing fields like id, is_active etc.

    def to_representation(self, instance):
        """Include related ChefRequest data if detailed context is requested."""
        representation = super().to_representation(instance)
        if self.context.get('detailed', False) and hasattr(instance.user, 'chefrequest'):
             # Import here to avoid potential circularity at module level
             from .serializers import ChefRequestSerializer
             representation['chef_request'] = ChefRequestSerializer(instance.user.chefrequest).data
        else:
             # If not detailed or no chef request, represent chef_request by its ID (or None)
             representation['chef_request'] = instance.user.chefrequest.id if hasattr(instance.user, 'chefrequest') else None
        return representation 