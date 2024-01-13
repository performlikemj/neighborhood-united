from rest_framework import serializers
from .models import GoalTracking, ChatThread

class GoalTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalTracking
        fields = ['id', 'goal_name', 'goal_description']

class ChatThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatThread
        fields = ['id', 'user', 'title', 'openai_thread_id', 'created_at']
