# Chef Kitchen (Ingredients & Dishes) - Standard Operating Procedure

## Overview

The **Kitchen** feature in Chef Hub is where chefs manage their culinary building blocks—ingredients and dishes. These form the foundation for meals, events, and meal plans throughout the platform.

---

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Key Concepts](#key-concepts)
3. [Managing Ingredients](#managing-ingredients)
4. [Managing Dishes](#managing-dishes)
5. [Building Meals](#building-meals)
6. [Nutritional Information](#nutritional-information)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details](#technical-details)

---

## Vision & Purpose

### The Problem
Without organized ingredient and dish management:
- Nutrition information is scattered or unknown
- Menu consistency is difficult to maintain
- Creating new meals requires starting from scratch
- Dietary information is hard to track

### The Solution
Kitchen provides structured culinary data management:
- **Ingredients** - Base components with nutritional data
- **Dishes** - Combinations of ingredients
- **Reusability** - Build meals from existing dishes
- **Nutrition** - Track calories, macros, etc.

![Kitchen Overview](./screenshots/kitchen-overview.png)
*The Kitchen section showing Ingredients, Dishes, and Meals management*

---

## Key Concepts

### Ingredient
A single food item or component:
- Name (e.g., "Chicken Breast")
- Nutritional data (calories, fat, carbs, protein)
- Can be used across multiple dishes

### Dish
A prepared recipe or menu item:
- Name (e.g., "Herb-Crusted Salmon")
- Contains one or more ingredients
- Can be marked as "Featured"
- Used to build meals

### Hierarchy

```
Ingredient → Dish → Meal → Event/Plan
    │          │       │
    │          │       └── Scheduled for customers
    │          └── Complete offering with price
    └── Building block with nutrition
```

---

## Managing Ingredients

### Accessing Ingredients
1. Log in to Chef Hub
2. Click **"Kitchen"** in the left sidebar
3. The Ingredients section is the first section on the page

![Ingredients Section](./screenshots/kitchen-ingredients.png)
*The Ingredients section with Add button and existing ingredients list*

### Creating an Ingredient

1. Click the **"Add"** button (with + icon) in the Ingredients section
2. Fill in the ingredient details:

   **Name** (required)
   - Clear, specific name
   - Example: "Boneless Skinless Chicken Breast"

   **Calories** (per 100g or serving)
   - Example: 165

   **Fat** (grams)
   - Example: 3.6

   **Carbohydrates** (grams)
   - Example: 0

   **Protein** (grams)
   - Example: 31

3. Click **"Add"** to save the ingredient

### Viewing Ingredients

Your ingredient list shows:
- Ingredient name displayed as a card/tile
- Each ingredient has an **"×"** button to remove it
- Ingredients are displayed in a horizontal scrollable list

### Duplicate Prevention

The system prevents duplicate ingredients:
- Warning appears if name already exists
- Modify name or use existing ingredient

### Deleting an Ingredient

1. Find the ingredient in your list
2. Click the **"×"** button on that ingredient
3. The ingredient is removed

> **Note**: Ingredients used in dishes may still appear in those dishes after deletion.

---

## Managing Dishes

### Accessing Dishes
In the Kitchen tab, the Dishes section appears as the second section below Ingredients.

![Dishes Section](./screenshots/kitchen-dishes.png)
*The Dishes section with Add button and existing dishes list*

### Creating a Dish

1. Click the **"Add"** button (with + icon) in the Dishes section
2. Fill in the dish details:

   **Name** (required)
   - Appetizing, descriptive name
   - Example: "Mediterranean Grilled Chicken Salad"

   **Featured** (optional)
   - Toggle ON to highlight this dish
   - Featured dishes may appear prominently

   **Ingredients**
   - Select ingredients from your list
   - Check boxes for each ingredient used
   - Multiple selections allowed

3. Click to save the dish

### Viewing Dishes

Your dish list shows:
- Dish name displayed as a card/tile
- Each dish has an **"×"** button to remove it
- Dishes are displayed in a horizontal scrollable list

### Deleting a Dish

1. Find the dish in your list
2. Click the **"×"** button on that dish
3. The dish is removed

> **Warning**: Dishes used in active meals cannot be deleted.

---

## Building Meals

### Dish → Meal Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                   BUILDING A MEAL                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   INGREDIENTS (Kitchen)                                     │
│   ├── Salmon Fillet                                         │
│   ├── Asparagus                                             │
│   ├── Lemon                                                 │
│   ├── Garlic                                                │
│   └── Olive Oil                                             │
│                                                             │
│                  ↓ combine into                             │
│                                                             │
│   DISH (Kitchen)                                            │
│   ├── Pan-Seared Salmon with Asparagus                      │
│   └── Uses: Salmon, Asparagus, Lemon, Garlic, Olive Oil     │
│                                                             │
│                  ↓ add with other dishes                    │
│                                                             │
│   MEAL (Meals tab)                                          │
│   ├── "Complete Salmon Dinner"                              │
│   ├── Price: $45                                            │
│   ├── Type: Dinner                                          │
│   ├── Dishes: Pan-Seared Salmon, Roasted Potatoes, Salad    │
│   └── Dietary: Pescatarian, Gluten-Free                     │
│                                                             │
│                  ↓ schedule                                 │
│                                                             │
│   EVENT or MEAL PLAN                                        │
│   └── Available for customers to order                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Creating Meals from Dishes

1. Go to **"Meals"** tab
2. Click **"+ Create Meal"**
3. Select dishes from your Kitchen inventory
4. Add pricing and details
5. Create the meal

### Dish Selection in Meal Form

The meal creation form includes:
- Searchable dish list
- Checkbox for each dish
- Filter by name
- Shows all your dishes

---

## Nutritional Information

### Why Track Nutrition?

Nutritional data helps:
- Meet customer dietary goals
- Calculate meal nutrition totals
- Support health-conscious customers
- Differentiate your offerings

### Nutritional Fields

| Field | Unit | Description |
|-------|------|-------------|
| **Calories** | kcal | Energy content |
| **Fat** | grams | Total fat |
| **Carbohydrates** | grams | Total carbs |
| **Protein** | grams | Protein content |

### Data Sources

Find nutritional information:
- USDA Food Database (free)
- Nutrition labels
- Calorie counting apps
- Food manufacturer websites

### Per-Serving Calculations

When adding nutrition data:
- Use consistent units (per 100g or per serving)
- Note your reference size
- Scale for actual portions used

### Example: Building Dish Nutrition

```
Herb-Crusted Salmon (per serving):

Ingredients:
├── Salmon Fillet (6oz): 350 cal, 15g fat, 0g carb, 40g protein
├── Olive Oil (1 tbsp): 120 cal, 14g fat, 0g carb, 0g protein
├── Fresh Herbs (1/4 cup): 5 cal, 0g fat, 1g carb, 0g protein
└── Lemon Juice (1 tbsp): 5 cal, 0g fat, 1g carb, 0g protein

Total: 480 cal, 29g fat, 2g carb, 40g protein
```

---

## Best Practices

### Ingredient Management

**1. Be Specific with Names**
- ✓ "Boneless Skinless Chicken Breast"
- ✗ "Chicken"

**2. Use Consistent Units**
- Pick one standard (per 100g or per serving)
- Apply consistently across all ingredients

**3. Include Common Ingredients**
Build a base library:
- Common proteins
- Staple vegetables
- Cooking oils
- Seasonings

**4. Update Regularly**
Add new ingredients as you:
- Develop new recipes
- Source new products
- Expand your cuisine range

### Dish Management

**1. Descriptive Names**
Include cooking method and key ingredients:
- ✓ "Pan-Seared Salmon with Lemon Butter"
- ✗ "Fish Dish"

**2. Feature Strategically**
Mark as featured:
- Signature dishes
- Customer favorites
- Seasonal highlights

**3. Build a Library**
Create dishes for:
- Frequent requests
- Signature items
- Seasonal rotations
- Special occasions

**4. Link All Ingredients**
Complete ingredient lists enable:
- Accurate prep planning
- Shopping list generation
- Nutrition calculations

### Organization Tips

**1. Name Conventions**
Use consistent naming:
- "[Cooking Method] [Protein/Main] with [Sauce/Sides]"
- "Grilled Chicken with Mediterranean Vegetables"

**2. Seasonal Grouping**
Consider dishes for:
- Spring: Light, fresh
- Summer: Grilled, salads
- Fall: Hearty, warm
- Winter: Comfort, rich

**3. Dietary Categories**
Tag dishes for:
- Vegetarian options
- Vegan options
- Gluten-free options
- Low-carb options

---

## Troubleshooting

### Can't create ingredient (duplicate)

**Cause**: Ingredient with same name exists.

**Solutions**:
1. Check existing ingredients list
2. Use the existing ingredient
3. Add distinguishing details to name
   - "Chicken Breast (organic)"
   - "Chicken Breast (conventional)"

### Ingredient not appearing in dish form

**Causes**:
- Page needs refresh
- Ingredient not saved
- Filter active

**Solutions**:
1. Refresh the page
2. Verify ingredient was created
3. Clear any search filters

### Dish not appearing in meal form

**Causes**:
- Dish not saved
- Filter hiding it
- Page cached

**Solutions**:
1. Check dish exists in Kitchen
2. Clear the filter field
3. Refresh the page

### Nutritional totals seem wrong

**Causes**:
- Inconsistent units
- Missing ingredient data
- Scaling issues

**Solutions**:
1. Verify all ingredients have nutrition data
2. Check units are consistent
3. Recalculate with correct portion sizes

### Can't delete an ingredient/dish

**Causes**:
- Used in active meals
- Used in orders
- System reference

**Solutions**:
1. Remove from meals first
2. Wait for orders to complete
3. Mark as inactive instead

---

## Technical Details

### Data Models

```python
Ingredient:
    name                # Ingredient name
    chef                # FK to Chef (ownership)
    calories            # kcal per unit
    fat                 # grams
    carbohydrates       # grams
    protein             # grams
    created_at          # Creation timestamp

Dish:
    name                # Dish name
    chef                # FK to Chef
    featured            # Featured flag
    ingredients         # M2M to Ingredient
    description         # Optional description
    created_at          # Creation timestamp

# Relationships
Dish.ingredients → Many-to-Many → Ingredient
Meal.dishes → Many-to-Many → Dish
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/meals/api/ingredients/` | GET | List ingredients |
| `/meals/api/chef/ingredients/` | POST | Create ingredient |
| `/meals/api/chef/ingredients/<id>/delete/` | DELETE | Delete ingredient |
| `/meals/api/dishes/` | GET | List dishes |
| `/meals/api/create-chef-dish/` | POST | Create dish |
| `/meals/api/dishes/<id>/` | PATCH | Update dish |
| `/meals/api/dishes/<id>/delete/` | DELETE | Delete dish |

### Request Examples

**Create Ingredient**
```json
{
  "name": "Atlantic Salmon",
  "calories": 208,
  "fat": 13,
  "carbohydrates": 0,
  "protein": 20
}
```

**Create Dish**
```json
{
  "name": "Herb-Crusted Salmon",
  "featured": true,
  "ingredients": [1, 5, 12, 15]
}
```

### Filter Parameters

**Ingredients**
```
/meals/api/ingredients/?chef_ingredients=true
```

**Dishes**
```
/meals/api/dishes/?chef_dishes=true
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial release with nutrition tracking |
| 1.1 | Dec 2025 | Updated with accurate UI walkthrough and screenshot placeholders |

---

*This SOP is maintained by the sautai development team. For questions or feature requests, contact support.*

