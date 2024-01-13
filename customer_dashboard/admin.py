from django.contrib import admin
from .models import GoalTracking, ChatThread

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


