# Chef Prep Planning - Standard Operating Procedure

## Overview

The **Prep Planning** feature in Chef Hub helps chefs optimize their resource usage by generating intelligent shopping lists that aggregate ingredients across all client meal plans within a specified time window. This reduces food waste, ensures efficient shopping, and provides smart timing recommendations based on ingredient shelf life.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Features](#key-features)
3. [How It Works](#how-it-works)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Understanding the Interface](#understanding-the-interface)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Independent chefs often serve multiple clients throughout the week, each with their own meal plans. Without proper planning:
- Ingredients are purchased separately for each client
- Perishables may spoil before use
- Bulk buying opportunities are missed
- Food waste increases costs and environmental impact

### The Solution
Prep Planning consolidates all upcoming meal commitments across ALL clients into a single, optimized shopping list with:
- **Ingredient aggregation** - Combines quantities across all meals/clients
- **Smart timing** - Tells you WHEN to buy each item based on shelf life
- **Batch cooking suggestions** - AI-generated tips for efficient prep
- **Purchase tracking** - Mark items as bought to track progress

---

## Key Features

### 1. Multi-Client Aggregation
The system pulls from **all three commitment sources**:
| Source | Description |
|--------|-------------|
| **Client Meal Plans** | Meal plans created for individual clients (primary workflow) |
| **Meal Events** | Public cooking events with customer orders |
| **Service Orders** | Booked chef service appointments |

### 2. Intelligent Ingredient Generation
For meals without structured ingredient data, AI automatically generates:
- Complete ingredient lists based on meal name
- Realistic quantities based on serving sizes
- Appropriate measurement units

### 3. Shelf Life Awareness
Each ingredient includes:
- Estimated shelf life (in days)
- Storage type (refrigerated, frozen, pantry, counter)
- Optimal purchase date to ensure freshness

### 4. Batch Cooking Recommendations
AI analyzes your upcoming meals and suggests:
- Which proteins can be cooked in bulk
- Grains that can be prepped ahead
- Vegetables to wash/chop in batches
- Sauces/marinades to make once

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    CHEF'S WEEK                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Client A (Smith Family)          Client B (Johnson's)     │
│   ├── Mon: Chicken Stir Fry        ├── Tue: Salmon Dinner   │
│   ├── Wed: Pasta Primavera         └── Thu: Caesar Salad    │
│   └── Fri: BBQ Ribs                                         │
│                                                             │
│   Meal Event (Saturday)                                     │
│   └── Community Brunch (12 orders)                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PREP PLAN GENERATOR                       │
│                                                             │
│   1. Collect all commitments (7 meals, 25 servings)         │
│   2. Extract/generate ingredients for each meal             │
│   3. Aggregate quantities across all meals                  │
│   4. Calculate shelf life for each ingredient               │
│   5. Determine optimal purchase dates                       │
│   6. Generate batch cooking suggestions                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   OPTIMIZED SHOPPING LIST                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   PURCHASE TODAY (Dec 6):                                   │
│   □ Chicken breast: 4.5 lbs (used in 3 meals)              │
│   □ Olive oil: 1 cup (used in 5 meals)                     │
│   □ Garlic: 2 heads (used in 6 meals)                      │
│                                                             │
│   PURCHASE WEDNESDAY (Dec 8):                               │
│   □ Fresh salmon: 2 lbs (Fri meal - 3 day shelf life)      │
│   □ Asparagus: 1.5 lbs (Fri meal - short shelf life)       │
│                                                             │
│   BATCH COOKING TIPS:                                       │
│   • Cook all chicken on Sunday, portion for each meal       │
│   • Make pasta sauce in bulk - freezes well                 │
│   • Prep all vegetables in one session                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Access Prep Planning
1. Log in to Chef Hub
2. Click **"Prep Planning"** in the left sidebar navigation
3. You'll see the Prep Planning dashboard

### Step 2: Generate a Prep Plan

#### Quick Plan (Recommended for Regular Use)
1. Click **"⚡ Quick Plan (7 days)"** button
2. System automatically:
   - Sets date range to next 7 days
   - Finds all your client meal plans
   - Generates optimized shopping list
3. Wait ~5-10 seconds for AI processing

#### Custom Date Range
1. Click **"📅 Custom Date Range"** button
2. Enter **Start Date** and **End Date**
3. Optionally add **Notes** for this plan
4. Click **"Generate Plan"**

### Step 3: Review Your Plan

After generation, you'll see:

#### Summary Cards
- **Total Meals**: Number of meal commitments
- **Total Servings**: Combined servings across all clients
- **Unique Ingredients**: Distinct ingredients to purchase
- **Clients Served**: Number of different clients

#### Shopping List
Toggle between views:
- **By Date**: Items grouped by suggested purchase date
- **By Category**: Items grouped by storage type (refrigerated, pantry, etc.)

Each item shows:
- Ingredient name
- Total quantity needed
- Unit of measurement
- Timing status (optimal/early/at_risk/urgent)
- Which meals use this ingredient

#### Batch Cooking Suggestions
AI-generated tips specific to your upcoming meals

#### Meals to Prepare
Timeline of all commitments showing:
- Date and meal type
- Client name
- Number of servings
- Type badge (Client Plan / Meal Event / Service)

### Step 4: Track Purchases

As you shop:
1. Click the **checkbox** next to each item when purchased
2. Item moves to "Purchased" section
3. Uncheck if needed to move back

### Step 5: Manage Plans

#### Regenerate
Click the **↻** icon to regenerate a plan with fresh data (useful when orders change)

#### Delete
Click the **🗑** icon to remove a plan

---

## Understanding the Interface

### Timing Status Indicators

| Status | Color | Meaning |
|--------|-------|---------|
| **Optimal** | Green | Perfect timing - buy on suggested date |
| **Early** | Blue | You have extra time - can buy earlier if convenient |
| **At Risk** | Yellow | Shelf life is tight - buy soon |
| **Urgent** | Red | May spoil before use - consider frozen alternatives |

### Commitment Types

| Badge | Source | Description |
|-------|--------|-------------|
| **Client Plan** | ChefMealPlan | Meal plans created for individual clients |
| **Meal Event** | ChefMealEvent | Public events with customer orders |
| **Service** | ChefServiceOrder | Booked service appointments |

---

## Best Practices

### 1. Plan Weekly on Sunday
Generate a fresh 7-day plan each Sunday to:
- Account for any changes from the previous week
- Get updated batch cooking suggestions
- Start the week organized

### 2. Review Before Shopping
Before heading to the store:
- Check the "By Date" view for today's purchases
- Note any "At Risk" or "Urgent" items
- Review batch cooking tips

### 3. Use Purchase Tracking
Mark items as purchased to:
- Avoid double-buying
- Track progress through your list
- Know what's still needed

### 4. Regenerate When Plans Change
If a client adds/removes meals:
1. Make changes in their meal plan
2. Click regenerate on your prep plan
3. Review updated shopping list

### 5. Batch Cook Strategically
Follow the AI suggestions to:
- Cook proteins in bulk at week start
- Prep vegetables once for multiple meals
- Make sauces/marinades ahead of time

---

## Troubleshooting

### "0 ingredients" showing

**Cause**: The meal plans have dates in the past, or the meals don't have ingredient data.

**Solution**:
1. Check that your client meal plans have **future dates**
2. Regenerate the prep plan
3. The system will use AI to generate ingredients for meals without structured data

### Plan shows fewer meals than expected

**Cause**: Only **future** commitments within the date range are included.

**Solution**:
1. Verify your client meal plan dates are within the selected range
2. Check that meal plan days are not marked as "skipped"
3. Ensure meal plan status is "draft" or "published" (not "archived")

### Ingredient quantities seem off

**Cause**: Quantities are scaled by serving size. AI-generated quantities are estimates.

**Solution**:
1. Check serving counts in your meal plans
2. AI estimates are based on standard portions - adjust as needed for specific clients
3. Consider adding RecipeIngredients to frequently-used dishes for precise quantities

### Batch suggestions not appearing

**Cause**: Groq API may not be configured or temporarily unavailable.

**Solution**:
1. General tips will appear as fallback
2. Check that GROQ_API_KEY is set in environment
3. Try regenerating the plan

---

## Technical Details

### Data Sources

The prep planning system aggregates from:

```python
# 1. Client Meal Plans (primary workflow)
ChefMealPlan → ChefMealPlanDay → ChefMealPlanItem

# 2. Meal Events
ChefMealEvent → ChefMealOrder (confirmed orders)

# 3. Service Orders
ChefServiceOrder (confirmed bookings)
```

### Ingredient Resolution Priority

1. **RecipeIngredient** - Structured data with exact quantities
2. **Dish.ingredients** - M2M relationship (quantities estimated)
3. **MealDish.ingredients** - JSON field with ingredient data
4. **Meal.composed_dishes** - JSON field for composed meals
5. **AI Generation** - Groq generates full ingredient list from meal name

### Shelf Life Determination

1. **Cached values** - If ingredient was looked up recently
2. **Groq API** - AI estimates shelf life based on ingredient name
3. **Fallback rules** - Keyword-based defaults (e.g., "milk" = 7 days)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chefs/api/me/prep-plans/` | GET | List all prep plans |
| `/chefs/api/me/prep-plans/` | POST | Create new plan |
| `/chefs/api/me/prep-plans/quick-generate/` | POST | Generate 7-day plan |
| `/chefs/api/me/prep-plans/<id>/` | GET | Get plan details |
| `/chefs/api/me/prep-plans/<id>/regenerate/` | POST | Regenerate plan |
| `/chefs/api/me/prep-plans/<id>/shopping-list/` | GET | Get shopping list |
| `/chefs/api/me/prep-plans/<id>/batch-suggestions/` | GET | Get batch tips |
| `/chefs/api/me/prep-plans/<id>/mark-purchased/` | POST | Mark items purchased |

### Sous Chef Integration

The prep planning tools are available through the Sous Chef AI assistant:

- "Show me my prep plan summary"
- "Generate a prep plan for next week"  
- "What's on my shopping list?"
- "Give me batch cooking suggestions"
- "What's the shelf life of salmon?"
- "What commitments do I have this week?"

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with multi-client support |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*
