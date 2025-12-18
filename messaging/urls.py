"""
URL patterns for messaging API.
"""
from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # List all conversations for current user
    path('api/conversations/', views.list_conversations, name='list_conversations'),
    
    # Get specific conversation with messages
    path('api/conversations/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    
    # Send message in conversation (REST fallback)
    path('api/conversations/<int:conversation_id>/send/', views.send_message, name='send_message'),
    
    # Mark conversation as read
    path('api/conversations/<int:conversation_id>/read/', views.mark_read, name='mark_read'),
    
    # Get or create conversation with a chef (for customers)
    path('api/conversations/with-chef/<int:chef_id>/', views.get_or_create_conversation, name='get_or_create_conversation'),
    
    # Get unread message counts
    path('api/unread-counts/', views.get_unread_counts, name='get_unread_counts'),
    
    # WebSocket health check (diagnostic endpoint)
    path('api/ws-health/', views.websocket_health_check, name='websocket_health_check'),
]


