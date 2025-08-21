from rest_framework import serializers
from .models import ChefRequest, Chef, ChefPhoto, ChefDefaultBanner
from django.contrib.auth import get_user_model
from local_chefs.models import PostalCode
from custom_auth.serializers import CustomUserSerializer
from custom_auth.models import Address


class ChefRequestSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = ChefRequest
        fields = ['id', 'user', 'experience', 'bio', 'profile_pic', 'is_approved']
        read_only_fields = ['id', 'user', 'is_approved']


class PostalCodePublicSerializer(serializers.ModelSerializer):
    postal_code = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()

    class Meta:
        model = PostalCode
        fields = ['postal_code', 'city', 'country']

    def get_postal_code(self, obj):
        return obj.display_code or obj.code

    def get_city(self, obj):
        # Attempt to infer a representative city from any user Address using this postal code and country
        try:
            city_qs = (
                Address.objects
                .filter(input_postalcode=obj.code, country=obj.country)
                .exclude(city__isnull=True)
                .exclude(city__exact='')
                .values_list('city', flat=True)
            )
            return city_qs.first() if city_qs.exists() else None
        except Exception:
            return None

    def get_country(self, obj):
        return {
            'code': getattr(obj.country, 'code', None),
            'name': getattr(obj.country, 'name', None),
        }


class ChefPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChefPhoto
        fields = ['id', 'image_url', 'title', 'caption', 'is_featured', 'created_at']
        read_only_fields = ['id', 'image_url', 'created_at']

    def get_image_url(self, obj):
        # Safe check: ImageFieldFile.url raises if no file; rely on name to detect presence
        if not obj.image or not getattr(obj.image, 'name', None):
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request is not None else url


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['username']


class ChefPublicSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    serving_postalcodes = PostalCodePublicSerializer(many=True, read_only=True)
    photos = ChefPhotoSerializer(many=True, read_only=True)
    profile_pic_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()

    class Meta:
        model = Chef
        fields = ['id', 'user', 'experience', 'bio', 'serving_postalcodes', 'profile_pic_url', 'banner_url', 'review_summary', 'photos']

    def get_profile_pic_url(self, obj):
        # Safe check: ImageFieldFile.url raises if no file; rely on name to detect presence
        if not obj.profile_pic or not getattr(obj.profile_pic, 'name', None):
            return None
        request = self.context.get('request')
        url = obj.profile_pic.url
        return request.build_absolute_uri(url) if request is not None else url

    def get_banner_url(self, obj):
        request = self.context.get('request')
        # Prefer chef's own banner
        if getattr(obj, 'banner_image', None) and getattr(obj.banner_image, 'name', None):
            url = obj.banner_image.url
            return request.build_absolute_uri(url) if request is not None else url
        # Fallback to most recent default banner if available
        default = ChefDefaultBanner.objects.first()
        if default and getattr(default.image, 'name', None):
            url = default.image.url
            return request.build_absolute_uri(url) if request is not None else url
        return None


class ChefMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chef
        fields = ['experience', 'bio', 'profile_pic', 'banner_image']
