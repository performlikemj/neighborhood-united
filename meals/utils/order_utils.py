import logging
from meals.models import ChefMealOrder, STATUS_PLACED

logger = logging.getLogger(__name__)

def create_chef_meal_orders(order):
    """
    Create ChefMealOrder instances for all chef meal events in an order.
    Returns the count of newly created records.
    """
    # Find OrderMeal instances with chef_meal_event
    chef_meal_order_meals = order.ordermeal_set.filter(
        chef_meal_event__isnull=False
    ).select_related('chef_meal_event')
    
    created_count = 0
    for order_meal in chef_meal_order_meals:
        # Determine the price to use
        price_to_use = order_meal.price_at_order if order_meal.price_at_order is not None else order_meal.chef_meal_event.current_price
        
        # Check if ChefMealOrder already exists to prevent duplicates
        chef_meal_order, created = ChefMealOrder.objects.get_or_create(
            order=order,
            meal_event=order_meal.chef_meal_event,
            customer=order.customer,
            defaults={
                'quantity': order_meal.quantity,
                'price_paid': price_to_use,
                'status': STATUS_PLACED,
            }
        )
        
        if created:
            created_count += 1
            logger.info(f"Created ChefMealOrder for order {order.id}, event {order_meal.chef_meal_event.id} at price {price_to_use}")
    
    return created_count 