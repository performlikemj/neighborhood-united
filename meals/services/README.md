# Chef Meal Order Service Layer

This service layer implements the business logic for chef meal ordering as described in the executive summary.

## Core Features

1. **Atomic Transactions**: All operations are wrapped in database transactions to prevent race conditions.
2. **Idempotency**: All operations support Stripe idempotency keys to prevent duplicate operations.
3. **Manual Capture Flow**: Holds card authorization at order time, captures payment at cutoff.
4. **Order Management**: Create, adjust quantity, and cancel orders with proper Stripe integration.

## Usage

### Creating an Order

```python
from meals.services.order_service import create_order

# Create a new order
order = create_order(
    user=request.user,
    event=event_object,
    qty=3,
    idem_key="unique-operation-id-123"
)
```

### Adjusting Quantity

```python
from meals.services.order_service import adjust_quantity

# Update order quantity
adjust_quantity(
    order=order_object,
    new_qty=5,
    idem_key="unique-operation-id-456"
)
```

### Cancelling an Order

```python
from meals.services.order_service import cancel_order

# Cancel an order
cancel_order(
    order=order_object,
    reason="customer_requested",
    idem_key="unique-operation-id-789"
)
```

## Technical Implementation

1. **Partial Unique Constraint**: Database enforces one active order per customer per event.
2. **Stripe Manual Capture**: Payment intents created with `capture_method='manual'`.
3. **Celery Tasks**: Scheduled tasks capture payments at cutoff time.
4. **n8n Webhooks**: Order events trigger webhooks for email notifications.

## Deployment

This service requires:

1. Properly configured Stripe API keys in settings.
2. N8N webhook URL in settings for notifications.
3. Celery configured for scheduled tasks.
4. PostgreSQL for the partial unique constraint. 