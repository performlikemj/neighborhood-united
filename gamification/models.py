from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from utils.redis_client import get, set, delete
from django.utils.translation import gettext_lazy as _
from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal
from datetime import timedelta
import uuid

User = get_user_model()

class UserProfile(models.Model):
    """Extended profile for gamification stats"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='gamification_profile')
    points = models.IntegerField(default=0, db_index=True)
    level = models.IntegerField(default=1)
    streak_count = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    total_meals_planned = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username}'s Gamification Profile"
    
    def add_points(self, amount):
        """Add points and update level if threshold reached."""
        self.points += amount
        # Level up every 100 points (configurable)
        new_level = (self.points // 100) + 1
        level_changed = new_level > self.level
        self.level = new_level
        self.save()
        
        # Clear cached leaderboard data
        delete('leaderboard_top_10')
        
        # Return whether level changed for notification purposes
        return level_changed
    
    def update_streak(self):
        """Update the login/meal planning streak."""
        today = timezone.now().date()
        
        if self.last_active_date:
            yesterday = today - timedelta(days=1)
            if self.last_active_date == yesterday:
                # Continued streak
                self.streak_count += 1
            elif self.last_active_date != today:
                # Streak broken, but not already updated today
                self.streak_count = 1
        else:
            # First activity
            self.streak_count = 1
            
        self.last_active_date = today
        self.save()
        
        # Return current streak for notification purposes
        return self.streak_count
    
    def increment_meals_planned(self):
        """Increment the total meals planned counter."""
        self.total_meals_planned += 1
        self.save()
        return self.total_meals_planned


class Achievement(models.Model):
    """Model for different achievements and badges users can earn"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class (e.g., 'fa-trophy')")
    points_reward = models.IntegerField(default=0)
    # Achievement criteria
    points_threshold = models.IntegerField(null=True, blank=True)
    streak_threshold = models.IntegerField(null=True, blank=True)
    meals_planned_threshold = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    """Records which achievements each user has earned and when"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    achieved_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'achievement')
        indexes = [
            models.Index(fields=['user', 'achievement']),
        ]
    
    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"


class WeeklyGoal(models.Model):
    """Weekly goals for users"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='weekly_goals')
    week_start_date = models.DateField()
    # Number of days aimed to plan for the week
    target_days = models.IntegerField(default=7)
    # Number of days actually planned
    completed_days = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'week_start_date')
    
    def __str__(self):
        return f"{self.user.username}'s goal for week of {self.week_start_date}"
    
    def calculate_progress(self):
        """Calculate the progress as a percentage (0-1)"""
        if self.target_days <= 0:
            return 1.0
        return min(1.0, self.completed_days / self.target_days)
    
    def update_progress(self):
        """Update completed days based on actual meal plan data"""
        # Calculate week end date (7 days from start)
        week_end_date = self.week_start_date + timedelta(days=6)
        
        # Find the meal plan for this week
        try:
            meal_plan = MealPlan.objects.get(
                user=self.user,
                week_start_date__lte=week_end_date,
                week_end_date__gte=self.week_start_date
            )
            
            # Count unique dates that have meals planned
            planned_dates = MealPlanMeal.objects.filter(
                meal_plan=meal_plan
            ).values_list('meal_date', flat=True).distinct()
            
            self.completed_days = len(set(planned_dates))
            
            # Mark as completed if reached target
            if self.completed_days >= self.target_days:
                self.completed = True
                
            self.save()
        except MealPlan.DoesNotExist:
            # No meal plan exists yet
            pass
        
        return self.calculate_progress()


class PointsTransaction(models.Model):
    """Record of points earned/spent by users"""
    TYPE_CHOICES = [
        ('earned', _('Earned')),
        ('spent', _('Spent')),
    ]
    
    SOURCE_CHOICES = [
        ('streak', _('Streak Bonus')),
        ('achievement', _('Achievement')),
        ('meal_plan', _('Meal Planning')),
        ('login', _('Daily Login')),
        ('weekly_goal', _('Weekly Goal Completion')),
        ('other', _('Other')),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='points_transactions')
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} {self.transaction_type} {self.amount} points from {self.source}"


class AnalyticsEvent(models.Model):
    """Events for analytics tracking"""
    EVENT_TYPES = [
        ('login', _('Login')),
        ('achievement', _('Achievement Earned')),
        ('level_up', _('Level Up')),
        ('meal_planned', _('Meal Planned')),
        ('streak_update', _('Streak Updated')),
        ('goal_completed', _('Weekly Goal Completed')),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='analytics_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    value = models.IntegerField(null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"{self.event_type} for {self.user.username} at {self.timestamp}"
