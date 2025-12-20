"""
Serializers for messaging API.
"""
from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for individual messages."""
    sender_name = serializers.SerializerMethodField()
    is_read = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_type', 'sender_name',
            'content', 'sent_at', 'read_at', 'is_read'
        ]
        read_only_fields = ['id', 'sender', 'sender_type', 'sent_at', 'read_at']
    
    def get_sender_name(self, obj):
        user = obj.sender
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.username


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversation list view."""
    customer_name = serializers.SerializerMethodField()
    chef_name = serializers.SerializerMethodField()
    chef_photo = serializers.SerializerMethodField()
    customer_photo = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'customer', 'chef', 'customer_name', 'chef_name',
            'chef_photo', 'customer_photo', 'last_message_at', 
            'last_message_preview', 'unread_count', 'created_at'
        ]
    
    def get_customer_name(self, obj):
        user = obj.customer
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.username
    
    def get_chef_name(self, obj):
        chef = obj.chef
        user = chef.user
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        return user.username
    
    def get_chef_photo(self, obj):
        if obj.chef.profile_pic:
            return obj.chef.profile_pic.url
        return None
    
    def get_customer_photo(self, obj):
        # Check if customer has a profile photo
        if hasattr(obj.customer, 'profile_pic') and obj.customer.profile_pic:
            return obj.customer.profile_pic.url
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return 0
        
        # Check if user is customer or chef
        if obj.customer_id == request.user.id:
            return obj.customer_unread_count
        
        # User is chef
        return obj.chef_unread_count


class ConversationDetailSerializer(ConversationSerializer):
    """Serializer for conversation detail view with messages."""
    messages = serializers.SerializerMethodField()
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']
    
    def get_messages(self, obj):
        # Get the last 50 messages by default
        messages = obj.messages.order_by('-sent_at')[:50]
        # Reverse to show oldest first
        messages = list(reversed(messages))
        return MessageSerializer(messages, many=True).data





