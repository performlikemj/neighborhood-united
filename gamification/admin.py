from django.contrib import admin
from .models import (
    UserProfile, 
    Achievement, 
    UserAchievement, 
    WeeklyGoal, 
    PointsTransaction,
    AnalyticsEvent
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'level', 'streak_count', 'total_meals_planned', 'last_active_date')
    search_fields = ('user__username', 'user__email')
    list_filter = ('level',)
    readonly_fields = ('last_active_date',)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'points_reward', 'points_threshold',
                  'streak_threshold', 'meals_planned_threshold')
    search_fields = ('name', 'description')


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'achieved_at', 'notified')
    search_fields = ('user__username', 'achievement__name')
    list_filter = ('notified', 'achieved_at')
    date_hierarchy = 'achieved_at'


@admin.register(WeeklyGoal)
class WeeklyGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'week_start_date', 'target_days', 'completed_days', 
                  'completed', 'progress_percentage')
    search_fields = ('user__username',)
    list_filter = ('completed', 'week_start_date')
    date_hierarchy = 'week_start_date'
    
    def progress_percentage(self, obj):
        """Display progress as a percentage"""
        progress = obj.calculate_progress() * 100
        return f"{progress:.1f}%"
    
    progress_percentage.short_description = "Progress"


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'source', 'description', 'timestamp')
    search_fields = ('user__username', 'description')
    list_filter = ('transaction_type', 'source', 'timestamp')
    date_hierarchy = 'timestamp'


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'value', 'timestamp')
    search_fields = ('user__username',)
    list_filter = ('event_type', 'timestamp')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
