#!/usr/bin/env python3
"""
Populate demo data for Chef Ferris's Insights dashboard.
Run with: python manage.py shell < scripts/populate_insights_demo_data.py
"""

import random
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from chefs.models import Chef
from custom_auth.models import CustomUser
from chef_services.models import (
    ChefServiceOffering,
    ChefServicePriceTier,
    ChefCustomerConnection,
    ChefServiceOrder,
)
from meals.models import Meal, ChefMealEvent, ChefMealOrder, Order

# Configuration
CHEF_ID = 1
NUM_DEMO_CUSTOMERS = 8
DAYS_OF_DATA = 90  # Generate 90 days of historical data

# Demo customer names
DEMO_CUSTOMERS = [
    ("alice", "Alice", "Johnson", "alice@demo.local"),
    ("bob", "Bob", "Smith", "bob@demo.local"),
    ("carol", "Carol", "Williams", "carol@demo.local"),
    ("david", "David", "Brown", "david@demo.local"),
    ("emma", "Emma", "Davis", "emma@demo.local"),
    ("frank", "Frank", "Miller", "frank@demo.local"),
    ("grace", "Grace", "Wilson", "grace@demo.local"),
    ("henry", "Henry", "Moore", "henry@demo.local"),
]

# Demo service offerings
DEMO_SERVICES = [
    ("home_chef", "Personal Chef Experience", "A personalized cooking experience in your home"),
    ("weekly_prep", "Weekly Meal Prep", "Healthy meals prepared for your entire week"),
    ("home_chef", "Dinner Party Catering", "Impress your guests with a custom-prepared dinner"),
    ("weekly_prep", "Family Meal Pack", "Nutritious family-sized portions for the week"),
]

def get_or_create_demo_customers(chef):
    """Create demo customer users and connections."""
    customers = []

    for username, first_name, last_name, email in DEMO_CUSTOMERS:
        # Create or get user
        user, created = CustomUser.objects.get_or_create(
            username=f"demo_{username}",
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "is_active": True,
            }
        )
        if created:
            user.set_password("demo123")
            user.save()
            print(f"  Created demo customer: {user.username}")

        # Create or update connection with varied responded_at dates
        days_ago = random.randint(5, 60)
        responded_at = timezone.now() - timedelta(days=days_ago)

        connection, conn_created = ChefCustomerConnection.objects.update_or_create(
            chef=chef,
            customer=user,
            defaults={
                "status": ChefCustomerConnection.STATUS_ACCEPTED,
                "initiated_by": ChefCustomerConnection.INITIATED_BY_CUSTOMER,
                "responded_at": responded_at,
            }
        )
        if conn_created:
            print(f"  Created connection for: {user.username}")

        customers.append(user)

    return customers


def get_or_create_demo_services(chef):
    """Create demo service offerings with price tiers."""
    offerings = []

    for service_type, title, description in DEMO_SERVICES:
        offering, created = ChefServiceOffering.objects.get_or_create(
            chef=chef,
            title=title,
            defaults={
                "service_type": service_type,
                "description": description,
                "active": True,
                "default_duration_minutes": 120 if service_type == "home_chef" else 180,
                "max_travel_miles": 15,
            }
        )
        if created:
            print(f"  Created service offering: {title}")

            # Create price tiers
            tier_configs = [
                (1, 2, 7500, "1-2 people"),
                (3, 4, 12000, "3-4 people"),
                (5, None, 18000, "5+ people"),
            ]

            for hh_min, hh_max, price_cents, label in tier_configs:
                ChefServicePriceTier.objects.create(
                    offering=offering,
                    household_min=hh_min,
                    household_max=hh_max,
                    desired_unit_amount_cents=price_cents,
                    currency="usd",
                    display_label=label,
                    active=True,
                )
            print(f"    Created {len(tier_configs)} price tiers")

        offerings.append(offering)

    return offerings


def get_existing_meals(chef):
    """Get chef's existing meals for meal events."""
    meals = list(Meal.objects.filter(chef=chef))
    print(f"  Found {len(meals)} existing meals for chef")
    return meals


def create_service_orders(chef, customers, offerings):
    """Create demo service orders with varied dates and statuses."""
    now = timezone.now()
    orders_created = 0

    for day_offset in range(DAYS_OF_DATA):
        # Roughly 0-2 service orders per day
        num_orders = random.choices([0, 1, 2], weights=[0.4, 0.4, 0.2])[0]

        for _ in range(num_orders):
            customer = random.choice(customers)
            offering = random.choice(offerings)

            # Get a valid tier for this offering
            tier = offering.tiers.filter(active=True).first()
            if not tier:
                continue

            order_date = now - timedelta(days=day_offset)

            # Determine status based on date
            if day_offset > 7:
                status = random.choice(["confirmed", "completed", "completed", "completed"])
            elif day_offset > 2:
                status = random.choice(["confirmed", "confirmed", "completed"])
            else:
                status = random.choice(["awaiting_payment", "confirmed"])

            # Service date is a few days after order date
            service_date = (order_date + timedelta(days=random.randint(2, 7))).date()

            try:
                order = ChefServiceOrder.objects.create(
                    customer=customer,
                    chef=chef,
                    offering=offering,
                    tier=tier,
                    household_size=random.randint(tier.household_min, tier.household_max or 6),
                    service_date=service_date,
                    service_start_time=f"{random.randint(10, 18)}:00:00",
                    status=status,
                )
                # Backdate the created_at
                ChefServiceOrder.objects.filter(pk=order.pk).update(created_at=order_date)
                orders_created += 1
            except Exception as e:
                pass  # Skip duplicates or validation errors

    print(f"  Created {orders_created} service orders")
    return orders_created


def create_meal_events_and_orders(chef, customers, meals):
    """Create demo meal events and orders."""
    now = timezone.now()
    events_created = 0
    orders_created = 0

    for day_offset in range(0, DAYS_OF_DATA, 3):  # Events every ~3 days
        meal = random.choice(meals)
        event_date = (now - timedelta(days=day_offset)).date()

        # Determine status based on date
        if day_offset > 3:
            event_status = "completed"
        elif day_offset > 0:
            event_status = "closed"
        else:
            event_status = "open"

        base_price = Decimal(str(random.randint(15, 35)))

        event = ChefMealEvent.objects.create(
            chef=chef,
            meal=meal,
            event_date=event_date,
            event_time=f"{random.randint(17, 19)}:00:00",
            order_cutoff_time=timezone.make_aware(
                timezone.datetime.combine(
                    event_date - timedelta(days=1),
                    timezone.datetime.min.time()
                )
            ),
            max_orders=random.randint(10, 20),
            min_orders=2,
            base_price=base_price,
            current_price=base_price - Decimal("3.00"),
            min_price=base_price - Decimal("8.00"),
            status=event_status,
        )
        events_created += 1

        # Create orders for this event
        num_orders = random.randint(2, 6)
        event_customers = random.sample(customers, min(num_orders, len(customers)))

        for customer in event_customers:
            # Determine order status based on event status
            if event_status == "completed":
                order_status = random.choice(["confirmed", "completed", "completed"])
            elif event_status == "closed":
                order_status = "confirmed"
            else:
                order_status = random.choice(["placed", "confirmed"])

            quantity = random.randint(1, 3)
            price_paid = (event.current_price * quantity)

            # Create an Order first (required by ChefMealOrder)
            order_obj = Order.objects.create(
                customer=customer,
                status="Completed" if order_status == "completed" else "Placed",
            )

            meal_order = ChefMealOrder.objects.create(
                order=order_obj,
                meal_event=event,
                customer=customer,
                quantity=quantity,
                unit_price=event.current_price,
                price_paid=price_paid,
                status=order_status,
            )

            # Backdate
            order_date = timezone.make_aware(
                timezone.datetime.combine(
                    event_date - timedelta(days=random.randint(1, 3)),
                    timezone.datetime.min.time()
                )
            ) + timedelta(hours=random.randint(8, 20))

            ChefMealOrder.objects.filter(pk=meal_order.pk).update(created_at=order_date)
            Order.objects.filter(pk=order_obj.pk).update(created_at=order_date)
            orders_created += 1

        # Update event order count
        event.orders_count = len(event_customers)
        event.save(update_fields=['orders_count'])

    print(f"  Created {events_created} meal events with {orders_created} orders")
    return events_created, orders_created


def main():
    print("\n" + "="*60)
    print("Populating Insights Demo Data for Chef Ferris")
    print("="*60 + "\n")

    # Get chef
    try:
        chef = Chef.objects.get(id=CHEF_ID)
        print(f"Found Chef: {chef.user.username} (ID: {chef.id})")
    except Chef.DoesNotExist:
        print(f"ERROR: Chef with ID {CHEF_ID} not found!")
        return

    with transaction.atomic():
        print("\n1. Creating demo customers and connections...")
        customers = get_or_create_demo_customers(chef)

        print("\n2. Creating demo service offerings...")
        offerings = get_or_create_demo_services(chef)

        print("\n3. Getting existing meals...")
        meals = get_existing_meals(chef)

        print("\n4. Creating service orders...")
        create_service_orders(chef, customers, offerings)

        print("\n5. Creating meal events and orders...")
        create_meal_events_and_orders(chef, customers, meals)

    print("\n" + "="*60)
    print("Demo data population complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
else:
    # When run via shell < script.py
    main()
