"""
Messaging models for real-time chat between customers and chefs.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversation(models.Model):
    """
    Represents a conversation between a customer and a chef.
    
    Each customer-chef pair has exactly one conversation.
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_conversations'
    )
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='chef_conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Denormalized fields for quick access
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=255, blank=True)
    
    # Unread counts for both parties
    customer_unread_count = models.PositiveIntegerField(default=0)
    chef_unread_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('customer', 'chef')
        ordering = ['-last_message_at', '-updated_at']
        indexes = [
            models.Index(fields=['customer', '-last_message_at']),
            models.Index(fields=['chef', '-last_message_at']),
        ]
    
    def __str__(self):
        return f"Conversation(customer={self.customer_id}, chef={self.chef_id})"
    
    def get_or_create_for_connection(customer, chef):
        """Get or create a conversation for a customer-chef connection."""
        conversation, created = Conversation.objects.get_or_create(
            customer=customer,
            chef=chef
        )
        return conversation, created
    
    def update_last_message(self, message):
        """Update denormalized fields when a new message is sent."""
        self.last_message_at = message.sent_at
        self.last_message_preview = message.content[:255] if message.content else ''
        self.save(update_fields=['last_message_at', 'last_message_preview', 'updated_at'])
    
    def increment_unread(self, for_recipient):
        """
        Increment unread count for the recipient.
        
        Args:
            for_recipient: 'customer' or 'chef'
        """
        if for_recipient == 'customer':
            self.customer_unread_count = models.F('customer_unread_count') + 1
        else:
            self.chef_unread_count = models.F('chef_unread_count') + 1
        self.save(update_fields=[f'{for_recipient}_unread_count'])
        self.refresh_from_db()
    
    def mark_read(self, by_user_type):
        """
        Mark all messages as read for the given user type.
        
        Args:
            by_user_type: 'customer' or 'chef'
        """
        if by_user_type == 'customer':
            self.customer_unread_count = 0
            self.save(update_fields=['customer_unread_count'])
            # Mark messages sent by chef as read
            self.messages.filter(
                sender_type='chef',
                read_at__isnull=True
            ).update(read_at=timezone.now())
        else:
            self.chef_unread_count = 0
            self.save(update_fields=['chef_unread_count'])
            # Mark messages sent by customer as read
            self.messages.filter(
                sender_type='customer',
                read_at__isnull=True
            ).update(read_at=timezone.now())


class Message(models.Model):
    """
    Individual message within a conversation.
    """
    SENDER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('chef', 'Chef'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    sender_type = models.CharField(
        max_length=10,
        choices=SENDER_TYPE_CHOICES,
        help_text="Whether the sender is the customer or chef in this conversation"
    )
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Optional metadata
    metadata = models.JSONField(null=True, blank=True, help_text="Extra data like attachments")
    
    class Meta:
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['conversation', 'sent_at']),
            models.Index(fields=['conversation', '-sent_at']),
            models.Index(fields=['sender', 'sent_at']),
        ]
    
    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"Message({self.sender_type}: {preview})"
    
    @property
    def is_read(self):
        return self.read_at is not None
    
    def mark_as_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=['read_at'])


