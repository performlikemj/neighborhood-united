from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'sender_type', 'content', 'sent_at', 'read_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'chef', 'last_message_at', 'customer_unread_count', 'chef_unread_count')
    list_filter = ('created_at',)
    search_fields = ('customer__username', 'customer__email', 'chef__user__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'sender_type', 'content_preview', 'sent_at', 'read_at')
    list_filter = ('sender_type', 'sent_at')
    search_fields = ('content', 'sender__username')
    readonly_fields = ('sent_at',)
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


