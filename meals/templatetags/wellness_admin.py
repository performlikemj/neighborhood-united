from datetime import datetime, timedelta
from django import template
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import MealPlan, Order
from chefs.models import Chef, ChefRequest
from reviews.models import Review

register = template.Library()


@register.simple_tag
def get_admin_metrics():
    """Return a dict of lightweight counts for the admin dashboard."""
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    metrics = {
        "users_total": CustomUser.objects.all().count(),
        # Active meal plans this week (inclusive)
        "meal_plans_active": MealPlan.objects.filter(week_start_date__lte=today, week_end_date__gte=today).count(),
        # Meal plans that changed and need re-approval
        "approvals_pending": MealPlan.objects.filter(has_changes=True, is_approved=False).count(),
        # Orders created today
        "orders_today": Order.objects.filter(order_date__date=today).count(),
        "chefs_total": Chef.objects.all().count(),
        # Reviews in last 7 days
        "reviews_week": Review.objects.filter(created_at__gte=week_ago).count(),
        # Optional: Chef requests pending (not shown by default, but handy)
        "chef_requests_pending": ChefRequest.objects.filter(is_approved=False).count(),
    }
    return metrics

