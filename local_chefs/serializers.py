# local_chefs/serializers.py
from rest_framework import serializers
from .models import PostalCode, ChefPostalCode, AdministrativeArea


class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = ['id', 'code', 'display_code', 'country', 'latitude', 'longitude', 'place_name']


class PostalCodeMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for postal codes in lists."""
    class Meta:
        model = PostalCode
        fields = ['id', 'code', 'display_code']


class ChefPostalCodeSerializer(serializers.ModelSerializer):
    # Use basic representation to avoid circular imports
    chef_id = serializers.IntegerField(source='chef.id', read_only=True)
    chef_username = serializers.CharField(source='chef.user.username', read_only=True)
    postal_code = PostalCodeSerializer(read_only=True)

    class Meta:
        model = ChefPostalCode
        fields = ['chef_id', 'chef_username', 'postal_code']


class AdministrativeAreaSerializer(serializers.ModelSerializer):
    """Full serializer for administrative areas."""
    parent_name = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)
    
    class Meta:
        model = AdministrativeArea
        fields = [
            'id', 'name', 'name_local', 'area_type', 'country',
            'parent', 'parent_name', 'full_path',
            'latitude', 'longitude', 'postal_code_count'
        ]
    
    def get_parent_name(self, obj):
        if obj.parent:
            return obj.parent.name
        return None


class AdministrativeAreaSearchSerializer(serializers.ModelSerializer):
    """Compact serializer for search results."""
    parent_name = serializers.SerializerMethodField()
    area_type_display = serializers.CharField(source='get_area_type_display', read_only=True)
    
    class Meta:
        model = AdministrativeArea
        fields = [
            'id', 'name', 'name_local', 'area_type', 'area_type_display',
            'country', 'parent_name', 'postal_code_count',
            'latitude', 'longitude'
        ]
    
    def get_parent_name(self, obj):
        if obj.parent:
            return obj.parent.name
        return None


class ChefServiceAreaSerializer(serializers.Serializer):
    """Serializer for chef's selected service areas with postal code counts."""
    area_id = serializers.IntegerField(source='id')
    name = serializers.CharField()
    name_local = serializers.CharField()
    area_type = serializers.CharField()
    country = serializers.CharField()
    parent_name = serializers.SerializerMethodField()
    postal_code_count = serializers.IntegerField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    
    def get_parent_name(self, obj):
        if hasattr(obj, 'parent') and obj.parent:
            return obj.parent.name
        return None