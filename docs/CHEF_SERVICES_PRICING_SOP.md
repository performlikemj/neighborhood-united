# Chef Services & Pricing - Standard Operating Procedure

## Overview

The **Services** feature in Chef Hub allows chefs to define and manage their service offerings with flexible pricing tiers. This enables professional presentation of your services with tiered pricing based on household size and service frequency.

![Services Overview](./screenshots/services-overview.png)
*The Services section showing create form and existing service offerings*

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Concepts](#key-concepts)
3. [Service Types](#service-types)
4. [How It Works](#how-it-works)
5. [Step-by-Step Guide](#step-by-step-guide)
6. [Pricing Tiers](#pricing-tiers)
7. [Target Customers](#target-customers)
8. [Managing Orders](#managing-orders)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Pricing personal chef services is challenging:
- Different household sizes require different pricing
- One-time vs. recurring services have different economics
- Custom services need flexibility
- Customers need clear pricing before booking

### The Solution
Services provides a structured pricing framework:
- **Service Offerings** - Define what you offer
- **Pricing Tiers** - Flexible pricing by household size
- **Recurring Options** - Weekly, monthly subscriptions
- **Target Customers** - Private offerings for specific clients

---

## Key Concepts

### Service Offering
A **Service Offering** is a specific service you provide:
- In-Home Chef services
- Weekly Meal Prep
- Custom service types

### Pricing Tier
A **Pricing Tier** defines pricing for a specific segment:
- Household size range (1-2 people, 3-4 people, etc.)
- One-time or recurring pricing
- Recurrence interval (weekly, monthly)

### Service Order
When a customer books your service, it creates a **Service Order**:
- Tracks the booking details
- Links to payment
- Maintains service history

---

## Service Types

| Type | Code | Description |
|------|------|-------------|
| **In-Home Chef** | `home_chef` | Personal chef services at customer's home |
| **Weekly Meal Prep** | `weekly_prep` | Regular meal preparation service |

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                   SERVICE STRUCTURE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   SERVICE OFFERING                                          │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ Title: Weekly Meal Prep                             │  │
│   │ Type: weekly_prep                                   │  │
│   │ Description: Fresh, healthy meals prepared weekly   │  │
│   │ Duration: 180 minutes                               │  │
│   │ Travel: Up to 15 miles                              │  │
│   │                                                     │  │
│   │ PRICING TIERS:                                      │  │
│   │ ┌─────────────────────────────────────────────────┐│  │
│   │ │ Tier 1: Individual (1-2 people)                 ││  │
│   │ │ $150/week - 5 meals included                    ││  │
│   │ └─────────────────────────────────────────────────┘│  │
│   │ ┌─────────────────────────────────────────────────┐│  │
│   │ │ Tier 2: Small Family (3-4 people)               ││  │
│   │ │ $250/week - 5 meals for the family              ││  │
│   │ └─────────────────────────────────────────────────┘│  │
│   │ ┌─────────────────────────────────────────────────┐│  │
│   │ │ Tier 3: Large Family (5+ people)                ││  │
│   │ │ $350/week - 5 meals for larger households       ││  │
│   │ └─────────────────────────────────────────────────┘│  │
│   │                                                     │  │
│   │ TARGET: All connected customers                     │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
│                            │                                │
│                            ▼                                │
│                                                             │
│   CUSTOMER BOOKING FLOW                                     │
│   ┌─────────────────────────────────────────────────────┐  │
│   │ 1. Customer views your service offerings            │  │
│   │ 2. Selects appropriate tier for their household     │  │
│   │ 3. Chooses date/time                                │  │
│   │ 4. Completes payment                                │  │
│   │ 5. Service Order created                            │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Access Services
1. Log in to Chef Hub
2. Click **"Services"** in the left sidebar
3. You'll see the **"Create service offering"** form and **"Your services"** section

![Services Page](./screenshots/services-create-form.png)
*The service creation form with all required fields*

### Step 2: Create a Service Offering

The "Create service offering" form contains:

1. **Service Type** (dropdown)
   - Select from available options:
     - **In-Home Chef** - Personal chef services at customer's home
     - **Weekly Meal Prep** - Regular meal preparation service

2. **Service Name** (text field)
   - Clear, descriptive name
   - Example: "Weekly Family Meal Prep"

3. **Description** (text area)
   - Placeholder: *"What does this service include?"*
   - Example: "5 complete dinners for your family, prepared fresh each week"

4. **Pricing Fields** (number inputs)
   - Price range or household size pricing
   - Define minimum and maximum values

5. **Additional Notes** (text field)
   - Placeholder: *"Special requirements, supplies, etc."*
   - Include any special requirements or what you provide

6. **Target Customers** (optional multiselect)
   - Leave blank for public services visible to everyone
   - Select specific customers for private offerings
   - Note displayed: *"Use the multiselect to target accepted customers. Leave it blank to keep the service visible to everyone."*

7. Click **"Create offering"** button to save

   **Max Travel (miles)**
   - How far you'll travel
   - Example: 15

   **Notes** (internal)
   - Private notes for yourself

3. Click **"Save"** to create the offering

### Step 3: Add Pricing Tiers

After creating an offering:

1. Find the offering in your list
2. Click **"Add Tier"** button
3. Configure the tier:

   **Household Size Range**
   - Minimum: e.g., 1
   - Maximum: e.g., 2
   
   **Display Label**
   - Customer-facing name
   - Example: "Individual/Couple"

   **Price**
   - Amount to charge
   - Example: 150.00

   **Recurring**
   - Toggle ON for subscription pricing
   - Select interval: Week or Month

   **Active**
   - Toggle to enable/disable

4. Click **"Save Tier"**
5. Repeat for additional tiers

### Step 4: Edit a Service Offering

1. Find the offering in your list
2. Click **"Edit"** button
3. Update the details
4. Click **"Update"**

### Step 5: Manage Pricing Tiers

#### Edit a Tier
1. Click the **"Edit"** icon next to the tier
2. Modify the settings
3. Click **"Save"**

#### Deactivate a Tier
1. Edit the tier
2. Toggle **"Active"** OFF
3. Tier remains but isn't shown to customers

### Step 6: Target Specific Customers

To create private offerings:

1. Edit the service offering
2. In **"Target Customers"** section
3. Select specific customers from your connections
4. Only selected customers will see this offering

Leave empty for public offerings visible to all connected customers.

---

## Pricing Tiers

### Tier Structure

Each tier defines:
| Field | Purpose | Example |
|-------|---------|---------|
| **Household Min** | Minimum household size | 1 |
| **Household Max** | Maximum household size | 2 |
| **Display Label** | Customer-facing name | "Individual/Couple" |
| **Price** | Amount charged | $150 |
| **Recurring** | Is this a subscription? | Yes |
| **Interval** | If recurring, how often | Weekly |
| **Active** | Is tier available? | Yes |

### Recommended Tier Examples

#### In-Home Chef Service (One-Time)

| Tier | Household | Price | Label |
|------|-----------|-------|-------|
| 1 | 1-2 | $200 | "Intimate Dinner" |
| 2 | 3-4 | $300 | "Family Dinner" |
| 3 | 5-8 | $450 | "Dinner Party" |
| 4 | 9+ | Custom | "Large Event" |

#### Weekly Meal Prep (Recurring)

| Tier | Household | Price | Interval | Label |
|------|-----------|-------|----------|-------|
| 1 | 1-2 | $150/week | Weekly | "Individual Plan" |
| 2 | 3-4 | $250/week | Weekly | "Family Plan" |
| 3 | 5+ | $350/week | Weekly | "Large Family Plan" |

### Pricing Strategies

**Cost-Plus Pricing**
1. Calculate ingredient costs
2. Add labor (hours × rate)
3. Add travel costs
4. Add profit margin (20-30%)

**Market-Based Pricing**
1. Research competitor rates
2. Position based on experience
3. Adjust for your service area

**Value-Based Pricing**
1. Consider time savings for customer
2. Factor in expertise/specialization
3. Premium for dietary accommodations

---

## Target Customers

### Public Offerings
- Leave target customers empty
- Visible to ALL connected customers
- Good for standard services

### Private Offerings
- Select specific customers
- Only selected customers see the offering
- Use for:
  - Custom arrangements
  - Special pricing
  - Exclusive services
  - Corporate clients

### Setting Up Target Customers

1. Edit the service offering
2. In the form, find **"Target Customers"**
3. Multi-select from your accepted connections
4. Save the offering

Customers not selected will not see this offering when browsing your services.

---

## Managing Orders

### Viewing Orders
1. Click **"Orders"** in the sidebar
2. Service orders appear in the list
3. Filter by status:
   - Awaiting Payment
   - Confirmed
   - Completed
   - Cancelled

### Order Information

Each order shows:
- Customer name
- Service title
- Tier selected
- Price
- Service date/time
- Status

### Order Workflow

```
PLACED → AWAITING_PAYMENT → CONFIRMED → COMPLETED
                                ↓
                           CANCELLED (if needed)
```

### Completing an Order
After service delivery:
1. Find the order
2. Update status to **"Completed"**
3. Order is recorded in history

### Cancelling an Order
If needed:
1. Find the order
2. Click **"Cancel"**
3. Refunds processed through Stripe (if applicable)

---

## Best Practices

### 1. Clear Tier Labels
Make it obvious which tier applies:
- ✓ "Individual/Couple (1-2 people)"
- ✓ "Family of 4"
- ✗ "Tier 1" (too vague)

### 2. Non-Overlapping Ranges
Ensure household ranges don't overlap:
- ✓ 1-2, 3-4, 5+
- ✗ 1-3, 3-5, 5+ (3 and 5 overlap)

### 3. Price Proportionally
Larger households = more work, but economies of scale:
- 1-2 people: $150
- 3-4 people: $250 (not $300)
- 5+ people: $350 (not $450)

### 4. Include Clear Descriptions
Describe what's included:
- Number of meals
- Portions per meal
- Included groceries (or not)
- Any restrictions

### 5. Set Realistic Travel Limits
Consider:
- Your actual service area
- Gas/time costs
- Traffic patterns

### 6. Use Private Offerings Strategically
Good uses:
- Loyal customer discounts
- Custom dietary accommodation
- Corporate accounts
- Trial pricing

### 7. Review Pricing Regularly
Adjust for:
- Ingredient cost changes
- Experience gained
- Market conditions
- Customer feedback

---

## Troubleshooting

### Customers can't see my services

**Causes**:
- No accepted connection
- Service has target customers set (they're not included)
- All tiers inactive

**Solutions**:
1. Verify customer is connected
2. Check target customer settings
3. Ensure at least one tier is active

### Tier not appearing

**Causes**:
- Tier marked inactive
- Price not set
- Household range issue

**Solutions**:
1. Edit tier and check "Active" toggle
2. Verify price is entered
3. Check household min/max are set

### Can't create recurring tier

**Causes**:
- Stripe not configured
- Missing required fields

**Solutions**:
1. Complete Stripe onboarding first
2. Ensure all required fields are filled

### Order stuck in "Awaiting Payment"

**Causes**:
- Customer didn't complete payment
- Payment failed
- Stripe webhook issue

**Solutions**:
1. Check with customer
2. Resend payment link
3. Verify Stripe dashboard
4. Contact support if persists

### Wrong price showing to customer

**Causes**:
- Tier not updated
- Cache issue
- Multiple tiers match

**Solutions**:
1. Verify tier settings
2. Ask customer to refresh
3. Check household size ranges don't overlap

---

## Technical Details

### Data Models

```python
ChefServiceOffering:
    chef                      # FK to Chef
    service_type              # 'home_chef' or 'weekly_prep'
    title                     # Service name
    description               # What's included
    default_duration_minutes  # Service duration
    max_travel_miles          # Travel radius
    notes                     # Internal notes
    target_customers          # M2M to Customer (empty = all)
    active                    # Is offering available
    created_at                # Creation timestamp

ChefServiceTier:
    offering                  # FK to ChefServiceOffering
    household_min             # Minimum household size
    household_max             # Maximum household size
    display_label             # Customer-facing name
    desired_unit_amount_cents # Price in cents
    currency                  # Currency code
    is_recurring              # Subscription pricing
    recurrence_interval       # 'week' or 'month'
    stripe_price_id           # Stripe Price object
    active                    # Is tier available
    
ChefServiceOrder:
    chef                      # FK to Chef
    customer                  # FK to Customer
    offering                  # FK to ChefServiceOffering
    tier                      # FK to ChefServiceTier
    status                    # Order status
    service_date              # Scheduled date
    service_start_time        # Scheduled time
    stripe_payment_intent_id  # Payment reference
    amount_cents              # Order amount
    created_at                # Order timestamp
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/services/my/offerings/` | GET | List chef's offerings |
| `/services/my/offerings/` | POST | Create offering |
| `/services/offerings/<id>/` | PATCH | Update offering |
| `/services/offerings/<id>/` | DELETE | Delete offering |
| `/services/offerings/<id>/tiers/` | POST | Add tier |
| `/services/tiers/<id>/` | PATCH | Update tier |
| `/services/tiers/<id>/` | DELETE | Delete tier |
| `/services/my/orders/` | GET | List chef's orders |
| `/services/orders/<id>/` | PATCH | Update order |

### Stripe Integration

Tiers are synced with Stripe:
- Each tier creates a Stripe Price object
- Recurring tiers use Stripe subscriptions
- One-time tiers use Checkout Sessions
- Prices are stored as `desired_unit_amount_cents`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with tiered pricing |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

