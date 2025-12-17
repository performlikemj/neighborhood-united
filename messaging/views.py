"""
REST API views for messaging.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef
from chef_services.models import ChefCustomerConnection
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, 
    ConversationDetailSerializer, 
    MessageSerializer
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_conversations(request):
    """
    List all conversations for the current user.
    
    Returns conversations where the user is either the customer or the chef.
    """
    user = request.user
    
    # Check if user is a chef
    try:
        chef = Chef.objects.get(user=user)
        is_chef = True
    except Chef.DoesNotExist:
        chef = None
        is_chef = False
    
    # Get conversations where user is customer or chef
    if is_chef:
        conversations = Conversation.objects.filter(
            Q(customer=user) | Q(chef=chef)
        ).select_related('customer', 'chef__user').order_by('-last_message_at', '-updated_at')
    else:
        conversations = Conversation.objects.filter(
            customer=user
        ).select_related('customer', 'chef__user').order_by('-last_message_at', '-updated_at')
    
    serializer = ConversationSerializer(
        conversations, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'conversations': serializer.data,
        'count': conversations.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation(request, conversation_id):
    """
    Get a specific conversation with messages.
    
    Automatically marks messages as read for the requesting user.
    """
    user = request.user
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Verify access
    is_customer = conversation.customer_id == user.id
    is_chef = False
    try:
        chef = Chef.objects.get(user=user)
        is_chef = conversation.chef_id == chef.id
    except Chef.DoesNotExist:
        pass
    
    if not is_customer and not is_chef:
        return Response(
            {'error': 'You do not have access to this conversation'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Mark as read
    user_type = 'customer' if is_customer else 'chef'
    conversation.mark_read(user_type)
    
    serializer = ConversationDetailSerializer(
        conversation, 
        context={'request': request}
    )
    
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, conversation_id):
    """
    Send a message in a conversation (REST fallback for WebSocket).
    """
    user = request.user
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Verify access and determine sender type
    is_customer = conversation.customer_id == user.id
    is_chef = False
    try:
        chef = Chef.objects.get(user=user)
        is_chef = conversation.chef_id == chef.id
    except Chef.DoesNotExist:
        pass
    
    if not is_customer and not is_chef:
        return Response(
            {'error': 'You do not have access to this conversation'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    content = request.data.get('content', '').strip()
    if not content:
        return Response(
            {'error': 'Message content is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    sender_type = 'customer' if is_customer else 'chef'
    
    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender=user,
        sender_type=sender_type,
        content=content
    )
    
    # Update conversation
    conversation.last_message_at = message.sent_at
    conversation.last_message_preview = content[:255]
    
    # Increment unread count for the other party
    if sender_type == 'customer':
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
    
    # Update connection activity
    try:
        connection = ChefCustomerConnection.objects.get(
            chef=conversation.chef,
            customer=conversation.customer
        )
        connection.update_activity('message')
    except ChefCustomerConnection.DoesNotExist:
        pass
    
    serializer = MessageSerializer(message)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, conversation_id):
    """
    Mark all messages as read in a conversation.
    """
    user = request.user
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Verify access
    is_customer = conversation.customer_id == user.id
    is_chef = False
    try:
        chef = Chef.objects.get(user=user)
        is_chef = conversation.chef_id == chef.id
    except Chef.DoesNotExist:
        pass
    
    if not is_customer and not is_chef:
        return Response(
            {'error': 'You do not have access to this conversation'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    user_type = 'customer' if is_customer else 'chef'
    conversation.mark_read(user_type)
    
    return Response({'status': 'ok'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def get_or_create_conversation(request, chef_id):
    """
    Get or create a conversation with a specific chef.
    
    Used when a customer wants to start messaging a chef.
    Only customers can initiate conversations.
    """
    user = request.user
    chef = get_object_or_404(Chef, id=chef_id)
    
    # Verify user is not the chef
    if chef.user_id == user.id:
        return Response(
            {'error': 'You cannot message yourself'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for existing connection
    connection = ChefCustomerConnection.objects.filter(
        chef=chef,
        customer=user,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    ).first()
    
    if not connection:
        return Response(
            {'error': 'You must be connected with this chef to send messages'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get or create conversation
    conversation, created = Conversation.objects.get_or_create(
        customer=user,
        chef=chef
    )
    
    serializer = ConversationDetailSerializer(
        conversation, 
        context={'request': request}
    )
    
    return Response({
        'conversation': serializer.data,
        'created': created
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_counts(request):
    """
    Get total unread message counts for the current user.
    """
    user = request.user
    
    # Check if user is a chef
    try:
        chef = Chef.objects.get(user=user)
        is_chef = True
    except Chef.DoesNotExist:
        chef = None
        is_chef = False
    
    # Count unread messages
    customer_unread = Conversation.objects.filter(
        customer=user,
        customer_unread_count__gt=0
    ).count()
    
    chef_unread = 0
    if is_chef:
        chef_unread = Conversation.objects.filter(
            chef=chef,
            chef_unread_count__gt=0
        ).count()
    
    total_unread = customer_unread + chef_unread
    
    return Response({
        'total_unread': total_unread,
        'customer_conversations_unread': customer_unread,
        'chef_conversations_unread': chef_unread,
    })

