"""
Service module for gamification business logic.
This module contains the core functions for handling gamification features.
"""
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

from .models import (
    UserProfile,
    Achievement,
    UserAchievement,
    WeeklyGoal,
    PointsTransaction,
    AnalyticsEvent
)

logger = logging.getLogger(__name__)

# Point reward constants
POINTS = {
    'daily_login': 5,
    'streak_day': 10,  # Additional points per day of streak
    'streak_milestone': 50,  # Extra points for reaching streak milestones (7, 14, 30 days)
    'meal_planned': 15,
    'weekly_goal_completed': 100,
}

# Streak milestones that trigger additional rewards
STREAK_MILESTONES = [7, 14, 30, 60, 90, 180, 365]


def get_or_create_profile(user):
    """Get or create a gamification profile for a user."""
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def award_points(user, amount, source, description=""):
    """Award points to a user and record the transaction."""
    profile = get_or_create_profile(user)
    
    with transaction.atomic():
        # Add points and check if user leveled up
        level_up = profile.add_points(amount)
        
        # Record the transaction
        transaction = PointsTransaction.objects.create(
            user=user,
            amount=amount,
            transaction_type='earned',
            source=source,
            description=description
        )
        
        # Record analytics event
        AnalyticsEvent.objects.create(
            user=user,
            event_type='level_up' if level_up else 'points_earned',
            value=amount,
            additional_data={
                'source': source,
                'new_level': profile.level if level_up else None,
                'total_points': profile.points
            }
        )
    
    # Check for achievements based on points
    check_achievements(user)
    
    return profile.points


def update_streak(user):
    """Update a user's streak and award points if appropriate."""
    profile = get_or_create_profile(user)
    
    # Store previous streak for comparison
    previous_streak = profile.streak_count
    
    # Update the streak
    new_streak = profile.update_streak()
    
    # Record streak update event
    AnalyticsEvent.objects.create(
        user=user,
        event_type='streak_update',
        value=new_streak
    )
    
    # If streak continued or started, award points
    if new_streak > 0:
        # Base login points
        award_points(
            user, 
            POINTS['daily_login'], 
            'login', 
            f"Daily login bonus (day {new_streak})"
        )
        
        # Additional streak points if streak is continuing
        if new_streak > 1:
            streak_points = POINTS['streak_day']
            award_points(
                user,
                streak_points,
                'streak',
                f"Streak bonus (day {new_streak})"
            )
        
        # Check for streak milestones
        for milestone in STREAK_MILESTONES:
            # Only award if we just reached this milestone
            if new_streak == milestone:
                milestone_points = POINTS['streak_milestone']
                award_points(
                    user,
                    milestone_points,
                    'streak',
                    f"Streak milestone reached: {milestone} days"
                )
                
    return new_streak


def register_meal_planned(user):
    """Record that a user has planned a meal and update stats."""
    profile = get_or_create_profile(user)
    
    with transaction.atomic():
        # Increment total meals planned counter
        total_meals = profile.increment_meals_planned()
        
        # Award points
        award_points(
            user,
            POINTS['meal_planned'],
            'meal_plan',
            "Meal planned"
        )
        
        # Record analytics event
        AnalyticsEvent.objects.create(
            user=user,
            event_type='meal_planned',
            value=total_meals
        )
    
    # Check for achievements based on meals planned
    check_achievements(user)
    
    return total_meals


def update_weekly_goal(user, week_start_date=None):
    """Update a user's weekly goal progress based on their meal plans."""
    if week_start_date is None:
        # Use current week
        today = timezone.now().date()
        # Find the start of the week (Monday)
        week_start_date = today - timedelta(days=today.weekday())
    
    # Get or create the weekly goal
    goal, created = WeeklyGoal.objects.get_or_create(
        user=user,
        week_start_date=week_start_date,
        defaults={'target_days': 7}  # Default to planning for all 7 days
    )
    
    # Update progress
    progress = goal.update_progress()
    
    # Check if goal was just completed
    if goal.completed and goal.completed_days >= goal.target_days:
        # Award points for completing the weekly goal
        award_points(
            user,
            POINTS['weekly_goal_completed'],
            'weekly_goal',
            f"Completed weekly meal planning goal ({goal.completed_days}/{goal.target_days} days)"
        )
        
        # Record analytics event
        AnalyticsEvent.objects.create(
            user=user,
            event_type='goal_completed',
            value=goal.completed_days,
            additional_data={
                'target_days': goal.target_days,
                'week_start': str(goal.week_start_date)
            }
        )
    
    return goal


def get_leaderboard(limit=10):
    """Get the top users by points for a leaderboard."""
    cache_key = f'leaderboard_top_{limit}'
    leaderboard = cache.get(cache_key)
    
    if leaderboard is None:
        # Query the top users
        top_profiles = UserProfile.objects.select_related('user').order_by('-points')[:limit]
        
        leaderboard = [
            {
                'username': profile.user.username,
                'points': profile.points,
                'level': profile.level,
                'streak': profile.streak_count
            }
            for profile in top_profiles
        ]
        
        # Cache for 1 hour
        cache.set(cache_key, leaderboard, 3600)
    
    return leaderboard


def check_achievements(user):
    """Check if a user has earned any new achievements."""
    profile = get_or_create_profile(user)
    
    # Get all achievements user hasn't earned yet
    earned_achievement_ids = UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
    
    # Check each type of achievement criteria
    new_achievements = []
    
    # Points-based achievements
    points_achievements = Achievement.objects.filter(
        points_threshold__lte=profile.points
    ).exclude(id__in=earned_achievement_ids)
    
    # Streak-based achievements
    streak_achievements = Achievement.objects.filter(
        streak_threshold__lte=profile.streak_count
    ).exclude(id__in=earned_achievement_ids)
    
    # Meals planned achievements
    meals_achievements = Achievement.objects.filter(
        meals_planned_threshold__lte=profile.total_meals_planned
    ).exclude(id__in=earned_achievement_ids)
    
    # Combine all eligible achievements
    eligible_achievements = list(points_achievements) + list(streak_achievements) + list(meals_achievements)
    
    # Make sure we don't have duplicates
    eligible_achievements = list({a.id: a for a in eligible_achievements}.values())
    
    with transaction.atomic():
        for achievement in eligible_achievements:
            # Award the achievement
            user_achievement = UserAchievement.objects.create(
                user=user,
                achievement=achievement,
                notified=False
            )
            
            # Award points if the achievement gives rewards
            if achievement.points_reward > 0:
                award_points(
                    user,
                    achievement.points_reward,
                    'achievement',
                    f"Achievement earned: {achievement.name}"
                )
            
            # Record analytics event
            AnalyticsEvent.objects.create(
                user=user,
                event_type='achievement',
                value=achievement.points_reward,
                additional_data={
                    'achievement_name': achievement.name,
                    'achievement_id': achievement.id
                }
            )
            
            new_achievements.append(user_achievement)
    
    return new_achievements


def get_unnotified_achievements(user):
    """Get achievements that the user hasn't been notified about yet."""
    unnotified = UserAchievement.objects.filter(
        user=user,
        notified=False
    ).select_related('achievement')
    
    return unnotified


def mark_achievements_as_notified(user):
    """Mark all of a user's unnotified achievements as notified."""
    UserAchievement.objects.filter(
        user=user,
        notified=False
    ).update(notified=True)


def get_weekly_goal_progress(user, week_start_date=None):
    """Get a user's current weekly goal progress."""
    if week_start_date is None:
        # Use current week
        today = timezone.now().date()
        # Find the start of the week (Monday)
        week_start_date = today - timedelta(days=today.weekday())
    
    try:
        goal = WeeklyGoal.objects.get(
            user=user,
            week_start_date=week_start_date
        )
        return {
            'progress': goal.calculate_progress(),
            'completed_days': goal.completed_days,
            'target_days': goal.target_days,
            'completed': goal.completed,
            'week_start_date': goal.week_start_date
        }
    except WeeklyGoal.DoesNotExist:
        return {
            'progress': 0.0,
            'completed_days': 0,
            'target_days': 7,  # Default
            'completed': False,
            'week_start_date': week_start_date
        } 