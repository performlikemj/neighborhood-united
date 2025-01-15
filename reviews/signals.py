# reviews/serializers.py
from rest_framework import serializers
from .models import Review
from meals.models import Meal, MealPlan

class ReviewSerializer(serializers.ModelSerializer):
    related_object = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'user', 'rating', 'comment', 'related_object']

    def get_related_object(self, obj):
        if isinstance(obj.content_object, Meal):
            return {"type": "Meal", "name": obj.content_object.name, "id": obj.content_object.id}
        elif isinstance(obj.content_object, MealPlan):
            return {"type": "MealPlan", "id": obj.content_object.id}
        return None