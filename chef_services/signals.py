"""
Signals for chef_services app.

Handles activity tracking on ChefCustomerConnection for multi-chef support.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='meals.ChefMealOrder')
def update_connection_order_activity(sender, instance, created, **kwargs):
    """
    Update last_order_at on ChefCustomerConnection when an order is created.
    """
    if not created:
        return
    
    from chef_services.models import ChefCustomerConnection
    
    try:
        # Get chef from the meal event
        chef = instance.meal_event.chef if instance.meal_event else None
        customer = instance.customer
        
        if chef and customer:
            ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).update(last_order_at=timezone.now())
            
            logger.debug(
                f"Updated order activity for connection: chef={chef.id}, customer={customer.id}"
            )
    except Exception as e:
        logger.warning(f"Failed to update order activity: {e}")


@receiver(post_save, sender='chef_services.ChefServiceOrder')
def update_connection_service_order_activity(sender, instance, created, **kwargs):
    """
    Update last_order_at on ChefCustomerConnection when a service order is confirmed.
    """
    # Only update when order becomes confirmed
    if instance.status != 'confirmed':
        return
    
    from chef_services.models import ChefCustomerConnection
    
    try:
        chef = instance.chef
        customer = instance.customer
        
        if chef and customer:
            ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).update(last_order_at=timezone.now())
            
            logger.debug(
                f"Updated service order activity for connection: chef={chef.id}, customer={customer.id}"
            )
    except Exception as e:
        logger.warning(f"Failed to update service order activity: {e}")


@receiver(post_save, sender='meals.ChefMealPlan')
def update_connection_plan_activity(sender, instance, **kwargs):
    """
    Update last_plan_update_at on ChefCustomerConnection when a meal plan is published.
    """
    # Only update when plan is published
    if instance.status != 'published':
        return
    
    from chef_services.models import ChefCustomerConnection
    
    try:
        chef = instance.chef
        customer = instance.customer
        
        if chef and customer:
            ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).update(last_plan_update_at=timezone.now())
            
            logger.debug(
                f"Updated plan activity for connection: chef={chef.id}, customer={customer.id}"
            )
    except Exception as e:
        logger.warning(f"Failed to update plan activity: {e}")


@receiver(post_save, sender='customer_dashboard.SousChefMessage')
def update_connection_message_activity(sender, instance, created, **kwargs):
    """
    Update last_message_at on ChefCustomerConnection when a sous chef message is created.
    """
    if not created:
        return
    
    from chef_services.models import ChefCustomerConnection
    
    try:
        thread = instance.thread
        chef = thread.chef
        customer = thread.customer
        
        if chef and customer:
            ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).update(last_message_at=timezone.now())
            
            logger.debug(
                f"Updated message activity for connection: chef={chef.id}, customer={customer.id}"
            )
    except Exception as e:
        logger.warning(f"Failed to update message activity: {e}")



