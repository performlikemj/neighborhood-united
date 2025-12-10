# Chef Meals & Events - Standard Operating Procedure

## Overview

The **Meals & Events** features in Chef Hub enable chefs to create meal offerings and schedule public cooking events. Meals serve as the building blocks for events, meal plans, and menu offerings.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Concepts](#key-concepts)
3. [Creating Meals](#creating-meals)
4. [Managing Events](#managing-events)
5. [Order Management](#order-management)
6. [Dynamic Pricing](#dynamic-pricing)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Running a personal chef business involves:
- Creating consistent meal offerings
- Managing public cooking events
- Handling orders and capacity
- Coordinating timing and logistics

### The Solution
Meals & Events provides comprehensive tools:
- **Meals** - Create reusable meal offerings with dishes
- **Events** - Schedule public events with capacity limits
- **Orders** - Track and manage customer orders
- **Pricing** - Dynamic pricing based on demand

---

## Key Concepts

### Meal
A **Meal** is a complete offering consisting of:
- One or more dishes
- Price point
- Meal type (Breakfast, Lunch, Dinner, Snack)
- Dietary preference tags
- Description

### Dish
A **Dish** is a single prepared item:
- Has a name and optional description
- Links to ingredients
- Can be marked as "Featured"
- Reusable across multiple meals

### Event
A **Meal Event** is a scheduled cooking opportunity:
- Based on a specific meal
- Has date, time, and location
- Limited capacity (max orders)
- Order cutoff time
- Dynamic pricing options

### Order
A **Meal Order** is when a customer books:
- Links to specific event
- Tracks quantity and payment
- Status workflow

---

## Creating Meals

### Step 1: Access Meals Tab
1. Log in to Chef Hub
2. Click **"Meals"** in the left sidebar
3. You'll see your meals list

### Step 2: Create a New Meal

1. Click **"+ Create Meal"** button
2. Fill in the meal details:

   **Name** (required)
   - Clear, appetizing name
   - Example: "Mediterranean Grilled Salmon Dinner"

   **Description** (required)
   - What's included, cooking style
   - Example: "Fresh Atlantic salmon with herb crust, roasted vegetables, and quinoa pilaf"

   **Meal Type**
   - Breakfast
   - Lunch
   - Dinner
   - Snack

   **Price** (required)
   - Base price per serving
   - Example: 35.00

   **Start Date** (optional)
   - When this meal becomes available
   - Leave blank for immediate availability

   **Dietary Preferences**
   - Tag applicable preferences
   - Multiple selections allowed

   **Select Dishes** (required)
   - Check boxes for dishes to include
   - Use the filter to search dishes

3. Click **"Create Meal"**

### Step 3: View Meal Details

Your meal card shows:
- Meal name and type
- Price
- Number of dishes included
- Dietary tags
- Edit/Delete options

### Step 4: Edit a Meal

1. Find the meal in your list
2. Click **"Edit"** button
3. Update any fields
4. Click **"Save"**

### Step 5: Delete a Meal

1. Find the meal in your list
2. Click **"Delete"** button
3. Confirm deletion

> **Note**: Meals linked to active events cannot be deleted.

---

## Managing Events

### Step 1: Access Events Tab
1. Log in to Chef Hub
2. Click **"Events"** in the left sidebar
3. You'll see upcoming and past events

### Step 2: Create a New Event

1. Click **"+ Create Event"** button
2. Fill in the event details:

   **Select Meal** (required)
   - Choose from your meals dropdown
   - This determines what you're cooking

   **Event Date** (required)
   - When the event takes place
   - Must be in the future

   **Event Time**
   - Service time
   - Default: 18:00 (6 PM)

   **Order Cutoff Date** (required)
   - Last day to accept orders
   - Should be before event date

   **Order Cutoff Time**
   - Specific cutoff time
   - Default: 12:00 (noon)

   **Base Price**
   - Starting price per order
   - Example: 35.00

   **Min Price** (optional)
   - Lowest price (for dynamic pricing)
   - Leave empty if no dynamic pricing

   **Max Orders**
   - Capacity limit
   - Example: 10

   **Min Orders**
   - Minimum to proceed
   - Example: 3

   **Description** (optional)
   - Event-specific details
   - Location, special notes

   **Special Instructions** (optional)
   - Internal prep notes

3. Click **"Create Event"**

### Step 3: View Event Details

Event cards show:
- Meal name
- Date and time
- Order cutoff
- Current orders vs. capacity
- Pricing
- Status

### Step 4: Manage Upcoming Events

**View Orders**
- Click the event to expand
- See list of orders
- Customer names and quantities

**Edit Event**
- Click "Edit" to modify details
- Only possible before cutoff

**Cancel Event**
- Click "Cancel"
- All orders are refunded
- Customers are notified

### Step 5: View Past Events

Toggle **"Show Past Events"** to see:
- Completed events
- Order history
- Revenue generated

---

## Order Management

### Order Workflow

```
PLACED → CONFIRMED → COMPLETED
            ↓
       CANCELLED (if needed)
```

### Viewing Orders
1. Click **"Orders"** in the sidebar
2. See all meal orders
3. Filter by status or date

### Order Information

Each order shows:
- Customer name
- Event/Meal name
- Quantity
- Total amount
- Status
- Order date

### Order Statuses

| Status | Meaning | Actions |
|--------|---------|---------|
| **Placed** | Order received | Confirm or Cancel |
| **Confirmed** | Accepted, awaiting service | Complete or Cancel |
| **Completed** | Service delivered | View only |
| **Cancelled** | Order cancelled | View only |

### Processing Orders

**Confirm an Order**
1. Review order details
2. Click "Confirm"
3. Customer is notified

**Complete an Order**
1. After service delivery
2. Click "Complete"
3. Order moves to history

**Cancel an Order**
1. Click "Cancel"
2. Provide reason (optional)
3. Refund processed automatically

---

## Dynamic Pricing

### How It Works

Dynamic pricing adjusts the price based on:
- Time until order cutoff
- Current order volume
- Supply and demand

### Configuration

Set in event creation:
- **Base Price**: Starting/maximum price
- **Min Price**: Lowest allowable price

### Price Calculation

```
If orders < min_orders:
  - Price discounted toward min_price
  - Encourages early orders
  
If orders > threshold:
  - Price increases toward base_price
  - Premium for high-demand events
```

### Example Scenario

```
Event: Sunday Brunch
Base Price: $45
Min Price: $35
Max Orders: 12
Min Orders: 4

Current Status:
- 2 orders placed
- 5 days until cutoff

Dynamic Price: $37.50 (discounted to attract orders)

After 8 orders:
- Price: $42.00 (near capacity premium)
```

---

## Best Practices

### Meal Creation

**1. Clear Naming**
- ✓ "Herb-Crusted Salmon with Roasted Vegetables"
- ✗ "Dinner Option 1"

**2. Detailed Descriptions**
Include:
- Main ingredients
- Cooking method
- Side dishes
- Portion size

**3. Accurate Pricing**
Consider:
- Ingredient costs
- Prep time
- Your hourly rate
- Market rates

**4. Tag Dietary Preferences**
Always tag applicable:
- Vegetarian/Vegan
- Gluten-free
- Allergens

### Event Management

**1. Realistic Capacity**
- Consider your kitchen capacity
- Factor in delivery logistics
- Leave buffer for quality

**2. Appropriate Cutoff Times**
- 24-48 hours minimum
- More time for complex meals
- Consider shopping needs

**3. Minimum Orders**
Set minimums that:
- Cover your costs
- Justify the effort
- Are achievable

**4. Regular Events**
Build customer habits:
- Weekly "Sunday Brunch"
- Monthly "Date Night Dinner"
- Seasonal specials

### Order Management

**1. Prompt Confirmations**
- Confirm orders within hours
- Builds customer confidence

**2. Clear Communication**
- Note any changes
- Provide pickup/delivery info
- Share special instructions

**3. Complete After Service**
- Mark complete same day
- Keeps records accurate
- Enables reviews

---

## Troubleshooting

### Can't create a meal

**Causes**:
- Missing required fields
- No dishes available
- Kitchen setup incomplete

**Solutions**:
1. Fill all required fields
2. Create dishes first in Kitchen tab
3. Complete chef profile

### Event not appearing to customers

**Causes**:
- Event date in past
- Order cutoff passed
- Maximum orders reached

**Solutions**:
1. Check event date is future
2. Verify cutoff hasn't passed
3. Increase max orders if needed

### Customer can't order

**Causes**:
- Not connected to you
- Event full
- Past cutoff time

**Solutions**:
1. Have them request connection
2. Create another event
3. Extend cutoff if possible

### Orders not showing

**Causes**:
- Filter applied
- Page needs refresh
- Payment pending

**Solutions**:
1. Clear any filters
2. Refresh the page
3. Check Stripe for payment status

### Event pricing not updating

**Causes**:
- Dynamic pricing not enabled
- Min price not set
- Calculation timing

**Solutions**:
1. Set both base and min price
2. Wait for recalculation
3. Refresh the page

---

## Technical Details

### Data Models

```python
Meal:
    chef                    # FK to Chef
    name                    # Meal name
    description             # Full description
    meal_type               # breakfast/lunch/dinner/snack
    price                   # Base price
    start_date              # Availability date
    dietary_preferences     # JSON array of tags
    dishes                  # M2M to Dish
    created_at              # Creation timestamp

ChefMealEvent:
    chef                    # FK to Chef
    meal                    # FK to Meal
    event_date              # Event date
    event_time              # Event time
    order_cutoff_time       # Cutoff datetime
    base_price              # Starting price
    min_price               # Floor price (dynamic)
    max_orders              # Capacity
    min_orders              # Minimum to proceed
    description             # Event details
    special_instructions    # Prep notes
    status                  # active/cancelled/completed
    created_at              # Creation timestamp

ChefMealOrder:
    event                   # FK to ChefMealEvent
    customer                # FK to Customer
    quantity                # Number ordered
    unit_price              # Price at order time
    total_amount            # Total charged
    status                  # placed/confirmed/completed/cancelled
    stripe_payment_id       # Payment reference
    created_at              # Order timestamp
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/meals/api/meals/` | GET | List chef's meals |
| `/meals/api/chef/meals/` | POST | Create meal |
| `/meals/api/chef/meals/<id>/` | PATCH | Update meal |
| `/meals/api/chef/meals/<id>/` | DELETE | Delete meal |
| `/meals/api/chef-meal-events/` | GET | List events |
| `/meals/api/chef-meal-events/` | POST | Create event |
| `/meals/api/chef-meal-events/<id>/` | PATCH | Update event |
| `/meals/api/chef-meal-events/<id>/` | DELETE | Delete event |
| `/meals/api/chef-meal-orders/` | GET | List orders |
| `/meals/api/chef-meal-orders/<id>/confirm/` | POST | Confirm order |
| `/meals/api/chef-meal-orders/<id>/complete/` | POST | Complete order |
| `/meals/api/chef-meal-orders/<id>/cancel/` | POST | Cancel order |

### Meal Types

```javascript
MEAL_TYPES = [
  { value: 'Breakfast', label: 'Breakfast' },
  { value: 'Lunch', label: 'Lunch' },
  { value: 'Dinner', label: 'Dinner' },
  { value: 'Snack', label: 'Snack' }
]
```

### Dietary Options

```javascript
DIETARY_OPTIONS = [
  'Vegetarian', 'Vegan', 'Pescatarian', 'Keto', 'Paleo',
  'Halal', 'Kosher', 'Gluten-Free', 'Low Sodium',
  'Mediterranean', 'Whole30', 'FODMAP'
]
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with events and dynamic pricing |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

