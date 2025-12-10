"""
WebSocket consumer for real-time chat between customers and chefs.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time chat messages.
    
    Connection URL: ws://.../ws/chat/<conversation_id>/
    
    Messages:
        - Incoming: {"type": "message", "content": "..."}
        - Outgoing: {"type": "message", "message": {...}}
        - Typing: {"type": "typing", "is_typing": true/false}
    """
    
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope.get('user')
        
        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Verify user has access to this conversation
        has_access = await self.verify_conversation_access()
        if not has_access:
            await self.close(code=4003)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark messages as read when user connects
        await self.mark_conversation_read()
    
    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', 'message')
            
            if msg_type == 'message':
                content = data.get('content', '').strip()
                if content:
                    message = await self.save_message(content)
                    
                    # Broadcast to room group
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': {
                                'id': message['id'],
                                'sender_id': message['sender_id'],
                                'sender_type': message['sender_type'],
                                'content': message['content'],
                                'sent_at': message['sent_at'],
                                'is_read': False,
                            }
                        }
                    )
            
            elif msg_type == 'typing':
                is_typing = data.get('is_typing', False)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': self.user.id,
                        'is_typing': is_typing,
                    }
                )
            
            elif msg_type == 'read':
                await self.mark_conversation_read()
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'messages_read',
                        'reader_id': self.user.id,
                    }
                )
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def chat_message(self, event):
        """Handle chat message event from group."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Handle typing indicator event from group."""
        # Don't send typing indicator to the sender
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'is_typing': event['is_typing']
            }))
    
    async def messages_read(self, event):
        """Handle messages read event from group."""
        if event['reader_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'read',
                'reader_id': event['reader_id']
            }))
    
    @database_sync_to_async
    def verify_conversation_access(self):
        """Check if user has access to this conversation."""
        from .models import Conversation
        from chefs.models import Chef
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            # Check if user is the customer
            if conversation.customer_id == self.user.id:
                self.user_type = 'customer'
                return True
            
            # Check if user is the chef
            try:
                chef = Chef.objects.get(user=self.user)
                if conversation.chef_id == chef.id:
                    self.user_type = 'chef'
                    return True
            except Chef.DoesNotExist:
                pass
            
            return False
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, content):
        """Save a new message to the database."""
        from .models import Conversation, Message
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            sender_type=self.user_type,
            content=content
        )
        
        # Update conversation denormalized fields
        conversation.last_message_at = message.sent_at
        conversation.last_message_preview = content[:255]
        
        # Increment unread count for the other party
        if self.user_type == 'customer':
            conversation.chef_unread_count += 1
        else:
            conversation.customer_unread_count += 1
        
        conversation.save(update_fields=[
            'last_message_at', 
            'last_message_preview', 
            'customer_unread_count', 
            'chef_unread_count',
            'updated_at'
        ])
        
        # Update ChefCustomerConnection activity timestamp
        from chef_services.models import ChefCustomerConnection
        try:
            connection = ChefCustomerConnection.objects.get(
                chef=conversation.chef,
                customer=conversation.customer
            )
            connection.update_activity('message')
        except ChefCustomerConnection.DoesNotExist:
            pass
        
        return {
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_type': message.sender_type,
            'content': message.content,
            'sent_at': message.sent_at.isoformat(),
        }
    
    @database_sync_to_async
    def mark_conversation_read(self):
        """Mark all messages as read for the current user."""
        from .models import Conversation
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            conversation.mark_read(self.user_type)
        except Conversation.DoesNotExist:
            pass
