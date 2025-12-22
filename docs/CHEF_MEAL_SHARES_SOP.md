# Chef Meals & Meal Shares - Standard Operating Procedure

## Overview

The **Meals & Meal Shares** features in Chef Hub enable chefs to create meal offerings and schedule group cooking opportunities. Meals serve as the building blocks for meal shares, meal plans, and menu offerings.

A **Meal Share** allows a chef to cook one meal for multiple customers, making it efficient for the chef and cost-effective for customers through dynamic group pricing.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Concepts](#key-concepts)
3. [Creating Meals](#creating-meals)
4. [Managing Meal Shares](#managing-meal-shares)
5. [Duplicating Meal Shares](#duplicating-meal-shares)
6. [Order Management](#order-management)
7. [Dynamic Pricing](#dynamic-pricing)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Running a personal chef business involves:
- Creating consistent meal offerings
- Serving multiple customers efficiently
- Handling orders and capacity
- Coordinating timing and logistics

### The Solution
Meals & Meal Shares provides comprehensive tools:
- **Meals** - Create reusable meal offerings with dishes
- **Meal Shares** - Schedule batch cooking for multiple customers
- **Orders** - Track and manage customer orders
- **Pricing** - Dynamic pricing that rewards group ordering

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

### Meal Share
A **Meal Share** is a scheduled group cooking opportunity:
- Based on a specific meal
- Has date, time, and order cutoff
- Limited capacity (max orders)
- Dynamic pricing based on number of orders
- Multiple customers share the same meal offering

### Order
A **Meal Share Order** is when a customer books:
- Links to specific meal share
- Tracks quantity and payment
- Status workflow

---

## Creating Meals

### Step 1: Access Menu Builder
1. Log in to Chef Hub
2. Click **"Menu Builder"** in the left sidebar
3. Navigate to the **"Meals"** sub-tab
4. You'll see your meals list

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

---

## Managing Meal Shares

### Step 1: Access Meal Shares Tab
1. Log in to Chef Hub
2. Click **"Services"** in the left sidebar
3. Select the **"Meal Shares"** sub-tab
4. You'll see upcoming and past meal shares

### Step 2: Create a New Meal Share

1. Fill in the meal share form:

   **Select Meal** (required)
   - Choose from your meals dropdown
   - This determines what you're cooking

   **Event Date** (required)
   - When you'll prepare and serve the meal
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
   - Lowest price when fully subscribed
   - Leave empty if no dynamic pricing

   **Max Orders**
   - Capacity limit
   - Example: 10

   **Min Orders**
   - Minimum orders needed to proceed
   - Example: 3

   **Description** (optional)
   - Meal share-specific details
   - Pickup location, special notes

   **Special Instructions** (optional)
   - Internal prep notes

2. Click **"Create Meal Share"**

### Step 3: View Meal Share Details

Meal share entries show:
- Meal name
- Date and time
- Current orders vs. capacity (e.g., "3/10")
- Status

### Step 4: Manage Upcoming Meal Shares

**View Orders**
- Click the meal share to expand
- See list of orders
- Customer names and quantities

**Cancel Meal Share**
- Click "Cancel"
- All orders are refunded
- Customers are notified

### Step 5: View Past Meal Shares

Click **"Show past"** to see:
- Completed meal shares
- Order history
- Revenue generated

---

## Duplicating Meal Shares

The **Duplicate** feature helps you quickly create recurring meal shares without re-entering all details.

### How to Duplicate

1. Find the meal share you want to duplicate (upcoming or past)
2. Click the **"Duplicate"** button next to it
3. The create form will be pre-filled with:
   - Same meal
   - Same pricing (base price, min price)
   - Same capacity settings
   - Same description and instructions
   - **New date** (defaults to tomorrow)
4. Adjust the date and time as needed
5. Click **"Create Meal Share"**

### Best Uses for Duplicate

- **Weekly recurring meals**: Duplicate last week's meal share for the same day next week
- **Popular meals**: Quickly recreate meals that sold well
- **Seasonal offerings**: Bring back successful meal shares from previous seasons

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
2. See all meal share orders
3. Filter by status or date

### Order Information

Each order shows:
- Customer name
- Meal share/Meal name
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

Dynamic pricing rewards group ordering - as more customers order the same meal share, the price decreases for everyone. This benefits:
- **Chefs**: Higher volume, efficient batch cooking
- **Customers**: Lower prices for popular meals

### Configuration

Set in meal share creation:
- **Base Price**: Starting/maximum price
- **Min Price**: Lowest price (floor)

### Price Calculation

```
For each order after the first:
  - Price drops by 5% of (base_price - min_price)
  - Price never goes below min_price
  - All existing orders get the new lower price
```

### Example Scenario

```
Meal Share: Sunday Lasagna Night
Base Price: $45
Min Price: $30
Max Orders: 12

Order 1: Customer pays $45
Order 2: Price drops to $44.25 (both customers)
Order 3: Price drops to $43.50 (all three)
...
Order 10+: Price reaches $30 minimum (everyone pays $30)
```

**Win-Win**: Early customers are incentivized to share the meal share with friends - when prices drop, everyone benefits!

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

### Meal Share Management

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

**4. Build Regular Schedule**
Create customer habits:
- Weekly "Sunday Brunch"
- Monthly "Date Night Dinner"
- Seasonal specials

**5. Use Duplicate Feature**
- Don't recreate from scratch
- Duplicate past successes
- Build consistent offerings

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

### Can't create a meal share

**Causes**:
- Payouts not set up
- No meals available
- Missing required fields

**Solutions**:
1. Complete Stripe Connect setup
2. Create meals first in Menu Builder
3. Fill all required fields

### Meal share not appearing to customers

**Causes**:
- Date in past
- Order cutoff passed
- Maximum orders reached

**Solutions**:
1. Check date is in future
2. Verify cutoff hasn't passed
3. Increase max orders if needed

### Customer can't order

**Causes**:
- Not in service area
- Meal share full
- Past cutoff time

**Solutions**:
1. Check your service areas
2. Create another meal share
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
    dietary_preferences     # JSON array of tags
    dishes                  # M2M to Dish
    created_at              # Creation timestamp

ChefMealEvent (Meal Share):
    chef                    # FK to Chef
    meal                    # FK to Meal
    event_date              # Meal share date
    event_time              # Service time
    order_cutoff_time       # Cutoff datetime
    base_price              # Starting price
    min_price               # Floor price (dynamic)
    current_price           # Current price (auto-updated)
    max_orders              # Capacity
    min_orders              # Minimum to proceed
    orders_count            # Current order count
    description             # Meal share details
    special_instructions    # Prep notes
    status                  # scheduled/open/completed/cancelled
    created_at              # Creation timestamp

ChefMealOrder:
    meal_event              # FK to ChefMealEvent
    customer                # FK to Customer
    quantity                # Number ordered
    unit_price              # Price at order time
    price_paid              # Total charged
    status                  # placed/confirmed/completed/cancelled
    stripe_payment_intent_id # Payment reference
    created_at              # Order timestamp
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/meals/api/meals/` | GET | List chef's meals |
| `/meals/api/chef/meals/` | POST | Create meal |
| `/meals/api/chef/meals/<id>/` | PATCH | Update meal |
| `/meals/api/chef/meals/<id>/` | DELETE | Delete meal |
| `/meals/api/chef-meal-events/` | GET | List meal shares |
| `/meals/api/chef-meal-events/` | POST | Create meal share |
| `/meals/api/chef-meal-events/<id>/update/` | PATCH | Update meal share |
| `/meals/api/chef-meal-events/<id>/cancel/` | POST | Cancel meal share |
| `/meals/api/chef-meal-events/<id>/duplicate/` | POST | Duplicate meal share |
| `/meals/api/chef-meal-orders/` | GET | List orders |
| `/meals/api/chef-meal-orders/<id>/confirm/` | POST | Confirm order |
| `/meals/api/chef-meal-orders/<id>/cancel/` | POST | Cancel order |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with events and dynamic pricing |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough |
| 2.0 | Dec 2025 | Renamed "Events" to "Meal Shares"; added Duplicate feature |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

