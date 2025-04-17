from django.contrib import admin
from .models import GoalTracking, ChatThread, AssistantEmailToken

# Admin class for GoalTracking
class GoalTrackingAdmin(admin.ModelAdmin):
    list_display = ('goal_name', 'goal_description', 'user')
    search_fields = ('goal_name', 'user__username')
    list_filter = ('user',)
    readonly_fields = ('user',)

# Register your models here
admin.site.register(GoalTracking, GoalTrackingAdmin)

# Admin class for ChatThread
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'openai_thread_id','user', 'created_at')
    search_fields = ('user__username',)
    list_filter = ('user', 'created_at')
    readonly_fields = ('user', 'created_at')

# Register ChatThread model
admin.site.register(ChatThread, ChatThreadAdmin)

# Register AssistantEmailToken model
class AssistantEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'last_used_at', 'is_active')
    list_filter = ('is_active', 'created_at', 'last_used_at')
    search_fields = ('user__email', 'user__username', 'token')
    readonly_fields = ('token', 'created_at')
    
    actions = ['deactivate_tokens', 'generate_new_tokens']
    
    def deactivate_tokens(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_tokens.short_description = "Deactivate selected tokens"
    
    def generate_new_tokens(self, request, queryset):
        for token_obj in queryset:
            if not token_obj.is_active:
                new_token = AssistantEmailToken.create_for_user(token_obj.user)
                self.message_user(request, f"Generated new token for {token_obj.user.email}: {new_token.token}")
    generate_new_tokens.short_description = "Generate new tokens for selected users"

admin.site.register(AssistantEmailToken, AssistantEmailTokenAdmin)


