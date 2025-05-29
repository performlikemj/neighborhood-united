from django.contrib import admin
from .models import GoalTracking, ChatThread, AssistantEmailToken, WeeklyAnnouncement, ChatSessionSummary, UserChatSummary, UserEmailSession, EmailAggregationSession, PreAuthenticationMessage
from django.utils import timezone

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
    list_display = ('user', 'auth_token', 'created_at', 'get_is_active', 'expires_at')
    list_filter = ('created_at', 'expires_at', 'used')
    search_fields = ('user__email', 'user__username', 'auth_token')
    readonly_fields = ('auth_token', 'created_at', 'expires_at')

    actions = ['deactivate_tokens', 'generate_new_tokens']

    def get_is_active(self, obj):
        from django.utils import timezone
        return not obj.used and obj.expires_at > timezone.now()
    get_is_active.short_description = 'Active'
    get_is_active.boolean = True

    def deactivate_tokens(self, request, queryset):
        queryset.update(used=True)
    deactivate_tokens.short_description = "Deactivate selected tokens"
    
    def generate_new_tokens(self, request, queryset):
        for token_obj in queryset:
            if token_obj.used:
                new_token = AssistantEmailToken.create_for_user(token_obj.user)
                self.message_user(request, f"Generated new token for {token_obj.user.email}: {new_token.auth_token}")
    generate_new_tokens.short_description = "Generate new tokens for selected users"

admin.site.register(AssistantEmailToken, AssistantEmailTokenAdmin)

# Admin class for UserEmailSession
class UserEmailSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_is_active', 'created_at', 'expires_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at',)
    
    actions = ['expire_sessions']
    
    def get_is_active(self, obj):
        return obj.expires_at > timezone.now()
    get_is_active.short_description = 'Active'
    get_is_active.boolean = True
    
    def expire_sessions(self, request, queryset):
        """Expire selected email sessions immediately"""
        count = queryset.filter(expires_at__gt=timezone.now()).update(expires_at=timezone.now() - timezone.timedelta(seconds=1))
        self.message_user(request, f"Expired {count} email sessions.")
    expire_sessions.short_description = "Expire selected sessions"

admin.site.register(UserEmailSession, UserEmailSessionAdmin)

# Admin class for EmailAggregationSession
class EmailAggregationSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_identifier', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__email', 'user__username', 'session_identifier')
    readonly_fields = ('session_identifier', 'created_at')
    
    actions = ['deactivate_sessions']
    
    def deactivate_sessions(self, request, queryset):
        """Deactivate selected aggregation sessions"""
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f"Deactivated {count} aggregation sessions.")
    deactivate_sessions.short_description = "Deactivate selected sessions"

admin.site.register(EmailAggregationSession, EmailAggregationSessionAdmin)

# Admin class for PreAuthenticationMessage
class PreAuthenticationMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'auth_token', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__username', 'auth_token__auth_token')
    readonly_fields = ('created_at',)

admin.site.register(PreAuthenticationMessage, PreAuthenticationMessageAdmin)

# Admin class for WeeklyAnnouncement
class WeeklyAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('week_start', 'country_display', 'content_preview', 'created_at', 'created_by')
    list_filter = ('week_start', 'country', 'created_at')
    search_fields = ('content', 'week_start')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('week_start', 'country', 'content')
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['duplicate_for_next_week', 'duplicate_for_current_week']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('created_at', 'created_by')
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        # Ensure the announcement starts on a Monday
        if obj.week_start.weekday() != 0:  # 0 = Monday
            from datetime import timedelta
            # Calculate the most recent Monday
            days_since_monday = obj.week_start.weekday()
            obj.week_start = obj.week_start - timedelta(days=days_since_monday)
            self.message_user(request, f"Week start date adjusted to the nearest Monday: {obj.week_start}", level=25)  # INFO level
        
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "created_by":
            # Limit created_by field to admin users only
            from django.contrib.auth import get_user_model
            kwargs["queryset"] = get_user_model().objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def country_display(self, obj):
        return obj.country.name if obj.country else "GLOBAL"
    country_display.short_description = "Target Country"
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Message Preview"
    
    def duplicate_for_next_week(self, request, queryset):
        """Create copies of selected announcements for next week"""
        from datetime import timedelta
        count = 0
        for announcement in queryset:
            # Create a new announcement for next week with same content
            new_week_start = announcement.week_start + timedelta(days=7)
            # Check if an announcement already exists for this week/country
            duplicate_exists = WeeklyAnnouncement.objects.filter(
                week_start=new_week_start,
                country=announcement.country
            ).exists()
            
            if not duplicate_exists:
                WeeklyAnnouncement.objects.create(
                    week_start=new_week_start,
                    country=announcement.country,
                    content=announcement.content,
                    created_by=request.user
                )
                count += 1
                
        self.message_user(
            request, 
            f"Created {count} new announcement(s) for next week. "
            f"{len(queryset) - count} skipped due to existing entries."
        )
    duplicate_for_next_week.short_description = "Duplicate for next week"
    
    def duplicate_for_current_week(self, request, queryset):
        """Duplicate announcements to the current week"""
        from django.utils import timezone
        
        # Get current week's Monday using the model's utility method
        current_week_start = WeeklyAnnouncement.get_week_start()
        
        count = 0
        for announcement in queryset:
            # Check if an announcement already exists for this week/country
            duplicate_exists = WeeklyAnnouncement.objects.filter(
                week_start=current_week_start,
                country=announcement.country
            ).exists()
            
            if not duplicate_exists:
                WeeklyAnnouncement.objects.create(
                    week_start=current_week_start,
                    country=announcement.country,
                    content=announcement.content,
                    created_by=request.user
                )
                count += 1
                
        self.message_user(
            request, 
            f"Created {count} new announcement(s) for current week. "
            f"{len(queryset) - count} skipped due to existing entries."
        )
    duplicate_for_current_week.short_description = "Duplicate for current week"

admin.site.register(WeeklyAnnouncement, WeeklyAnnouncementAdmin)

@admin.register(ChatSessionSummary)
class ChatSessionSummaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'thread', 'summary_date', 'status', 'updated_at')
    list_filter = ('status', 'summary_date')
    search_fields = ('user__username', 'user__email', 'summary')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'thread')
    date_hierarchy = 'summary_date'

@admin.register(UserChatSummary)
class UserChatSummaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'last_summary_date', 'updated_at')
    list_filter = ('status', 'last_summary_date')
    search_fields = ('user__username', 'user__email', 'summary')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user',)
    date_hierarchy = 'last_summary_date'


