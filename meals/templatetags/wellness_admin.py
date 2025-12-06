from datetime import datetime, timedelta
from django import template
from django.utils import timezone
from django.db.models import Sum

from custom_auth.models import CustomUser
from meals.models import MealPlan, Order
from chefs.models import Chef, ChefRequest, ChefPaymentLink
from chef_services.models import ChefCustomerConnection, ChefServiceOrder
from crm.models import Lead
from reviews.models import Review

register = template.Library()


@register.simple_tag
def get_admin_metrics():
    """Return a dict of lightweight counts for the admin dashboard."""
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Chef CRM metrics
    metrics = {
        # Core counts
        "users_total": CustomUser.objects.all().count(),
        "chefs_total": Chef.objects.all().count(),
        "chefs_verified": Chef.objects.filter(is_verified=True).count(),
        "chefs_active": Chef.objects.filter(is_verified=True, is_on_break=False).count(),
        
        # Chef-Customer Connections
        "connections_pending": ChefCustomerConnection.objects.filter(status="pending").count(),
        "connections_active": ChefCustomerConnection.objects.filter(status="accepted").count(),
        
        # Service Orders
        "service_orders_total": ChefServiceOrder.objects.count(),
        "service_orders_confirmed": ChefServiceOrder.objects.filter(status="confirmed").count(),
        "service_orders_draft": ChefServiceOrder.objects.filter(status="draft").count(),
        "service_orders_month": ChefServiceOrder.objects.filter(created_at__gte=month_ago).count(),
        
        # CRM Leads
        "leads_total": Lead.objects.filter(is_deleted=False).count(),
        "leads_new": Lead.objects.filter(status="new", is_deleted=False).count(),
        "leads_qualified": Lead.objects.filter(status="qualified", is_deleted=False).count(),
        "leads_won": Lead.objects.filter(status="won", is_deleted=False).count(),
        "leads_this_week": Lead.objects.filter(created_at__gte=week_ago, is_deleted=False).count(),
        
        # Payment Links
        "payment_links_pending": ChefPaymentLink.objects.filter(status="pending").count(),
        "payment_links_paid_month": ChefPaymentLink.objects.filter(status="paid", paid_at__gte=month_ago).count(),
        
        # Legacy meal plan metrics
        "meal_plans_active": MealPlan.objects.filter(week_start_date__lte=today, week_end_date__gte=today).count(),
        "approvals_pending": MealPlan.objects.filter(has_changes=True, is_approved=False).count(),
        "orders_today": Order.objects.filter(order_date__date=today).count(),
        
        # Reviews
        "reviews_week": Review.objects.filter(created_at__gte=week_ago).count(),
        
        # Chef requests
        "chef_requests_pending": ChefRequest.objects.filter(is_approved=False).count(),
    }
    
    # Calculate revenue from paid payment links this month
    paid_this_month = ChefPaymentLink.objects.filter(
        status="paid", 
        paid_at__gte=month_ago
    ).aggregate(total=Sum('paid_amount_cents'))['total'] or 0
    metrics['revenue_month_cents'] = paid_this_month
    metrics['revenue_month_display'] = f"${paid_this_month / 100:,.2f}" if paid_this_month else "$0"
    
    return metrics

