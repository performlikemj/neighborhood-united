# customer_dashboard/serializers.py
from rest_framework import serializers
from .models import ChatThread


class ChatThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatThread
        fields = ['id', 'user', 'title', 'openai_thread_id', 'created_at', 'latest_response_id']

