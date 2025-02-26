from django.db.models.signals import post_save, post_delete, m2m_changed
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal

from .services import (
    update_streak,
    register_meal_planned,
    update_weekly_goal,
    check_achievements
)

import logging

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def handle_user_login(sender, user, request, **kwargs):
    """Update streak and award points when a user logs in."""
    try:
        update_streak(user)
    except Exception as e:
        logger.error(f"Error in gamification login handler: {str(e)}")


@receiver(post_save, sender=MealPlanMeal)
def handle_meal_added(sender, instance, created, **kwargs):
    """Award points when a user adds a meal to their meal plan."""
    if created:  # Only trigger on new meal plans, not updates
        try:
            # Get the user from the meal plan
            user = instance.meal_plan.user
            
            # Register the meal planned
            register_meal_planned(user)
            
            # Update the weekly goal progress
            week_start_date = instance.meal_plan.week_start_date
            update_weekly_goal(user, week_start_date)
        except Exception as e:
            logger.error(f"Error in gamification meal handler: {str(e)}")


@receiver(post_save, sender=MealPlan)
def handle_meal_plan_created(sender, instance, created, **kwargs):
    """Setup weekly goal when a meal plan is created."""
    if created:
        try:
            user = instance.user
            
            # Create/update the weekly goal for this meal plan's week
            update_weekly_goal(user, instance.week_start_date)
        except Exception as e:
            logger.error(f"Error in gamification meal plan handler: {str(e)}")


# Register custom signal handlers for other events
# You can add more handlers here for other gamification triggers 