from rest_framework import serializers
from .models import GoalTracking, ChatThread, UserHealthMetrics, CalorieIntake

class GoalTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalTracking
        fields = ['id', 'goal_name', 'goal_description']

class ChatThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatThread
        fields = ['id', 'user', 'title', 'openai_thread_id', 'created_at']


class UserHealthMetricsSerializer(serializers.ModelSerializer):
    date_recorded = serializers.DateField(format='%Y-%m-%d')  # Ensure date-only format

    class Meta:
        model = UserHealthMetrics
        fields = ['id', 'user', 'date_recorded', 'weight', 'bmi', 'mood', 'energy_level']


class CalorieIntakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalorieIntake
        fields = ['id', 'user', 'meal_name', 'meal_description', 'portion_size', 'date_recorded']

