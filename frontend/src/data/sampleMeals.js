/**
 * Sample Meals Catalog for Client-Side Preview
 * 
 * This module provides a curated catalog of sample meals and utilities
 * for generating personalized meal plan previews during onboarding.
 * All filtering happens client-side for instant reactivity.
 */

// Days and meal types for plan generation
export const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
export const MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner']

/**
 * Sample meals catalog (~55 meals)
 * Each meal includes:
 * - id: unique identifier
 * - name: display name
 * - description: brief description
 * - meal_type: 'breakfast' | 'lunch' | 'dinner'
 * - tags: dietary compatibility tags (Vegetarian, Vegan, Gluten-Free, etc.)
 * - avoidAllergens: allergens this meal contains (users with these allergies should avoid)
 */
export const SAMPLE_MEALS = [
  // ============================================
  // BREAKFAST (15 meals)
  // ============================================
  {
    id: 'b1',
    name: 'Greek Yogurt Parfait with Fresh Berries',
    description: 'Creamy Greek yogurt layered with seasonal berries, honey, and crunchy granola.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'High-Protein'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'b2',
    name: 'Avocado Toast with Poached Eggs',
    description: 'Whole grain toast topped with mashed avocado, perfectly poached eggs, and microgreens.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'High-Protein'],
    avoidAllergens: ['Egg', 'Wheat', 'Gluten']
  },
  {
    id: 'b3',
    name: 'Overnight Oats with Maple and Walnuts',
    description: 'Creamy oats soaked overnight with almond milk, maple syrup, and toasted walnuts.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Vegan', 'Dairy-Free'],
    avoidAllergens: ['Tree nuts', 'Gluten']
  },
  {
    id: 'b4',
    name: 'Spinach and Mushroom Omelette',
    description: 'Fluffy three-egg omelette filled with sautéed spinach, mushrooms, and herbs.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Keto', 'High-Protein', 'Gluten-Free'],
    avoidAllergens: ['Egg']
  },
  {
    id: 'b5',
    name: 'Fresh Fruit Bowl with Coconut',
    description: 'A colorful mix of seasonal fruits topped with shredded coconut and lime zest.',
    meal_type: 'breakfast',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'Paleo'],
    avoidAllergens: []
  },
  {
    id: 'b6',
    name: 'Shakshuka with Crusty Bread',
    description: 'Eggs poached in spiced tomato sauce with bell peppers, served with warm bread.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Halal'],
    avoidAllergens: ['Egg', 'Wheat', 'Gluten']
  },
  {
    id: 'b7',
    name: 'Chia Seed Pudding with Mango',
    description: 'Chia seeds soaked in coconut milk, layered with fresh mango and passion fruit.',
    meal_type: 'breakfast',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: []
  },
  {
    id: 'b8',
    name: 'Smoked Salmon Bagel',
    description: 'Toasted bagel with cream cheese, smoked salmon, capers, and fresh dill.',
    meal_type: 'breakfast',
    tags: ['Pescatarian', 'High-Protein'],
    avoidAllergens: ['Fish', 'Wheat', 'Gluten', 'Milk']
  },
  {
    id: 'b9',
    name: 'Banana Pancakes with Maple Syrup',
    description: 'Fluffy buttermilk pancakes studded with banana slices, drizzled with pure maple syrup.',
    meal_type: 'breakfast',
    tags: ['Vegetarian'],
    avoidAllergens: ['Wheat', 'Gluten', 'Milk', 'Egg']
  },
  {
    id: 'b10',
    name: 'Acai Bowl with Granola',
    description: 'Thick acai blend topped with fresh berries, banana, granola, and honey drizzle.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Vegan', 'Dairy-Free'],
    avoidAllergens: ['Tree nuts']
  },
  {
    id: 'b11',
    name: 'Vegetable Frittata',
    description: 'Baked egg dish loaded with zucchini, tomatoes, onions, and fresh herbs.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Gluten-Free', 'Keto', 'High-Protein'],
    avoidAllergens: ['Egg', 'Milk']
  },
  {
    id: 'b12',
    name: 'Almond Butter Toast with Banana',
    description: 'Whole grain toast spread with almond butter, topped with sliced banana and honey.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Vegan', 'Dairy-Free'],
    avoidAllergens: ['Tree nuts', 'Wheat', 'Gluten']
  },
  {
    id: 'b13',
    name: 'Breakfast Burrito Bowl',
    description: 'Scrambled eggs over rice with black beans, salsa, avocado, and cheese.',
    meal_type: 'breakfast',
    tags: ['Vegetarian', 'Gluten-Free', 'High-Protein'],
    avoidAllergens: ['Egg', 'Milk']
  },
  {
    id: 'b14',
    name: 'Coconut Milk Smoothie Bowl',
    description: 'Tropical smoothie bowl with coconut milk, pineapple, and toasted coconut flakes.',
    meal_type: 'breakfast',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'Paleo'],
    avoidAllergens: []
  },
  {
    id: 'b15',
    name: 'Steel Cut Oatmeal with Berries',
    description: 'Hearty steel cut oats cooked with cinnamon, topped with mixed berries and maple.',
    meal_type: 'breakfast',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free'],
    avoidAllergens: ['Gluten']
  },

  // ============================================
  // LUNCH (18 meals)
  // ============================================
  {
    id: 'l1',
    name: 'Mediterranean Quinoa Bowl',
    description: 'Fluffy quinoa with cucumber, tomatoes, olives, feta cheese, and lemon dressing.',
    meal_type: 'lunch',
    tags: ['Vegetarian', 'Gluten-Free', 'High-Protein'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'l2',
    name: 'Grilled Chicken Caesar Salad',
    description: 'Romaine lettuce with grilled chicken, parmesan, croutons, and creamy Caesar dressing.',
    meal_type: 'lunch',
    tags: ['High-Protein', 'Halal'],
    avoidAllergens: ['Milk', 'Egg', 'Wheat', 'Gluten', 'Fish']
  },
  {
    id: 'l3',
    name: 'Asian Vegetable Stir-Fry with Rice',
    description: 'Crisp vegetables in ginger-soy sauce served over steamed jasmine rice.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free'],
    avoidAllergens: ['Soy']
  },
  {
    id: 'l4',
    name: 'Roasted Vegetable Wrap',
    description: 'Warm tortilla filled with roasted vegetables, hummus, and fresh herbs.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free'],
    avoidAllergens: ['Wheat', 'Gluten', 'Sesame']
  },
  {
    id: 'l5',
    name: 'Lentil Soup with Herbs',
    description: 'Hearty red lentil soup with carrots, celery, and aromatic spices.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'High-Protein'],
    avoidAllergens: ['Celery']
  },
  {
    id: 'l6',
    name: 'Tuna Niçoise Salad',
    description: 'Classic French salad with seared tuna, green beans, potatoes, olives, and eggs.',
    meal_type: 'lunch',
    tags: ['Pescatarian', 'Gluten-Free', 'High-Protein', 'Dairy-Free'],
    avoidAllergens: ['Fish', 'Egg']
  },
  {
    id: 'l7',
    name: 'Falafel Bowl with Tahini',
    description: 'Crispy falafel with hummus, tabbouleh, pickled vegetables, and tahini drizzle.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free', 'Halal'],
    avoidAllergens: ['Wheat', 'Gluten', 'Sesame']
  },
  {
    id: 'l8',
    name: 'Turkey and Avocado Sandwich',
    description: 'Sliced turkey breast with avocado, bacon, lettuce, and tomato on sourdough.',
    meal_type: 'lunch',
    tags: ['High-Protein'],
    avoidAllergens: ['Wheat', 'Gluten']
  },
  {
    id: 'l9',
    name: 'Thai Peanut Noodle Salad',
    description: 'Rice noodles with shredded vegetables, edamame, and creamy peanut dressing.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free'],
    avoidAllergens: ['Peanuts', 'Soy']
  },
  {
    id: 'l10',
    name: 'Greek Salad with Grilled Halloumi',
    description: 'Fresh tomatoes, cucumbers, and olives with grilled halloumi cheese.',
    meal_type: 'lunch',
    tags: ['Vegetarian', 'Gluten-Free', 'Keto'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'l11',
    name: 'Black Bean Tacos',
    description: 'Soft corn tortillas filled with seasoned black beans, pico de gallo, and lime crema.',
    meal_type: 'lunch',
    tags: ['Vegetarian', 'Gluten-Free'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'l12',
    name: 'Miso Soup with Tofu',
    description: 'Traditional Japanese soup with silken tofu, wakame seaweed, and green onions.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free', 'Low-Calorie'],
    avoidAllergens: ['Soy']
  },
  {
    id: 'l13',
    name: 'Caprese Panini',
    description: 'Pressed sandwich with fresh mozzarella, tomatoes, basil, and balsamic glaze.',
    meal_type: 'lunch',
    tags: ['Vegetarian'],
    avoidAllergens: ['Milk', 'Wheat', 'Gluten']
  },
  {
    id: 'l14',
    name: 'Chicken Shawarma Plate',
    description: 'Spiced chicken with rice pilaf, garlic sauce, pickled turnips, and fresh salad.',
    meal_type: 'lunch',
    tags: ['High-Protein', 'Halal', 'Dairy-Free'],
    avoidAllergens: []
  },
  {
    id: 'l15',
    name: 'Buddha Bowl',
    description: 'Nourishing bowl with roasted sweet potato, chickpeas, greens, and tahini dressing.',
    meal_type: 'lunch',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: ['Sesame']
  },
  {
    id: 'l16',
    name: 'Shrimp Spring Rolls',
    description: 'Fresh rice paper rolls with shrimp, vermicelli, herbs, and peanut dipping sauce.',
    meal_type: 'lunch',
    tags: ['Pescatarian', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: ['Shellfish', 'Peanuts']
  },
  {
    id: 'l17',
    name: 'Spinach and Goat Cheese Salad',
    description: 'Baby spinach with warm goat cheese, candied walnuts, and balsamic vinaigrette.',
    meal_type: 'lunch',
    tags: ['Vegetarian', 'Gluten-Free'],
    avoidAllergens: ['Milk', 'Tree nuts']
  },
  {
    id: 'l18',
    name: 'Veggie Burger with Sweet Potato Fries',
    description: 'House-made veggie patty on brioche bun with all the fixings and crispy fries.',
    meal_type: 'lunch',
    tags: ['Vegetarian'],
    avoidAllergens: ['Wheat', 'Gluten', 'Soy']
  },

  // ============================================
  // DINNER (22 meals)
  // ============================================
  {
    id: 'd1',
    name: 'Herb-Crusted Salmon with Asparagus',
    description: 'Wild-caught salmon with a herb crust, served with roasted asparagus and lemon.',
    meal_type: 'dinner',
    tags: ['Pescatarian', 'Gluten-Free', 'High-Protein', 'Keto', 'Paleo'],
    avoidAllergens: ['Fish']
  },
  {
    id: 'd2',
    name: 'Chicken Tikka Masala with Basmati Rice',
    description: 'Tender chicken in aromatic tomato-cream sauce, served with fluffy basmati rice.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Halal'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'd3',
    name: 'Vegetable Pad Thai',
    description: 'Rice noodles with crispy tofu, vegetables, peanuts, and tangy tamarind sauce.',
    meal_type: 'dinner',
    tags: ['Vegan', 'Vegetarian', 'Dairy-Free'],
    avoidAllergens: ['Peanuts', 'Soy']
  },
  {
    id: 'd4',
    name: 'Grilled Lamb Chops with Mint',
    description: 'Perfectly grilled lamb chops with mint yogurt sauce and roasted potatoes.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Halal', 'Gluten-Free'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'd5',
    name: 'Eggplant Parmesan',
    description: 'Breaded eggplant layered with marinara sauce and melted mozzarella cheese.',
    meal_type: 'dinner',
    tags: ['Vegetarian'],
    avoidAllergens: ['Milk', 'Wheat', 'Gluten', 'Egg']
  },
  {
    id: 'd6',
    name: 'Shrimp Scampi with Linguine',
    description: 'Succulent shrimp in garlic butter sauce tossed with linguine and fresh parsley.',
    meal_type: 'dinner',
    tags: ['Pescatarian', 'High-Protein'],
    avoidAllergens: ['Shellfish', 'Wheat', 'Gluten', 'Milk']
  },
  {
    id: 'd7',
    name: 'Stuffed Bell Peppers',
    description: 'Bell peppers filled with seasoned rice, black beans, corn, and melted cheese.',
    meal_type: 'dinner',
    tags: ['Vegetarian', 'Gluten-Free'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'd8',
    name: 'Thai Green Curry with Tofu',
    description: 'Creamy coconut curry with crispy tofu, bamboo shoots, and Thai basil.',
    meal_type: 'dinner',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: ['Soy']
  },
  {
    id: 'd9',
    name: 'Beef Bulgogi with Kimchi',
    description: 'Korean-style marinated beef with steamed rice and traditional kimchi.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Dairy-Free'],
    avoidAllergens: ['Soy', 'Wheat', 'Gluten']
  },
  {
    id: 'd10',
    name: 'Mushroom Risotto',
    description: 'Creamy arborio rice with wild mushrooms, parmesan, and fresh thyme.',
    meal_type: 'dinner',
    tags: ['Vegetarian', 'Gluten-Free'],
    avoidAllergens: ['Milk']
  },
  {
    id: 'd11',
    name: 'Grilled Steak with Chimichurri',
    description: 'Perfectly grilled ribeye with Argentine chimichurri sauce and roasted vegetables.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Gluten-Free', 'Keto', 'Paleo', 'Dairy-Free'],
    avoidAllergens: []
  },
  {
    id: 'd12',
    name: 'Coconut Curry Shrimp',
    description: 'Shrimp simmered in coconut curry with jasmine rice and crispy shallots.',
    meal_type: 'dinner',
    tags: ['Pescatarian', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: ['Shellfish']
  },
  {
    id: 'd13',
    name: 'Spaghetti Bolognese',
    description: 'Classic Italian meat sauce slow-simmered with tomatoes, served over spaghetti.',
    meal_type: 'dinner',
    tags: ['High-Protein'],
    avoidAllergens: ['Wheat', 'Gluten']
  },
  {
    id: 'd14',
    name: 'Baked Falafel with Couscous',
    description: 'Crispy baked falafel served over fluffy couscous with cucumber yogurt sauce.',
    meal_type: 'dinner',
    tags: ['Vegetarian', 'Halal'],
    avoidAllergens: ['Wheat', 'Gluten', 'Milk', 'Sesame']
  },
  {
    id: 'd15',
    name: 'Teriyaki Salmon Bowl',
    description: 'Glazed salmon over sushi rice with edamame, pickled ginger, and sesame.',
    meal_type: 'dinner',
    tags: ['Pescatarian', 'Dairy-Free', 'High-Protein'],
    avoidAllergens: ['Fish', 'Soy', 'Sesame']
  },
  {
    id: 'd16',
    name: 'Vegetable Lasagna',
    description: 'Layers of pasta, ricotta, spinach, zucchini, and marinara topped with mozzarella.',
    meal_type: 'dinner',
    tags: ['Vegetarian'],
    avoidAllergens: ['Wheat', 'Gluten', 'Milk', 'Egg']
  },
  {
    id: 'd17',
    name: 'Lemon Herb Roasted Chicken',
    description: 'Whole roasted chicken with lemon, garlic, and herbs, served with roasted potatoes.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Gluten-Free', 'Dairy-Free', 'Paleo', 'Halal'],
    avoidAllergens: []
  },
  {
    id: 'd18',
    name: 'Cauliflower Steak with Romesco',
    description: 'Roasted cauliflower steak with smoky romesco sauce and crispy capers.',
    meal_type: 'dinner',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'Keto'],
    avoidAllergens: ['Tree nuts']
  },
  {
    id: 'd19',
    name: 'Pork Tenderloin with Apple Chutney',
    description: 'Herb-crusted pork tenderloin with warm apple chutney and mashed potatoes.',
    meal_type: 'dinner',
    tags: ['High-Protein', 'Gluten-Free', 'Dairy-Free'],
    avoidAllergens: []
  },
  {
    id: 'd20',
    name: 'Chickpea and Spinach Curry',
    description: 'Hearty chickpea curry with spinach, tomatoes, and warm spices over basmati rice.',
    meal_type: 'dinner',
    tags: ['Vegan', 'Vegetarian', 'Gluten-Free', 'Dairy-Free', 'High-Protein'],
    avoidAllergens: []
  },
  {
    id: 'd21',
    name: 'Miso Glazed Cod',
    description: 'Tender cod fillet with sweet miso glaze, bok choy, and sesame rice.',
    meal_type: 'dinner',
    tags: ['Pescatarian', 'Dairy-Free', 'High-Protein'],
    avoidAllergens: ['Fish', 'Soy', 'Sesame']
  },
  {
    id: 'd22',
    name: 'Black Bean Enchiladas',
    description: 'Corn tortillas filled with black beans and cheese, smothered in red enchilada sauce.',
    meal_type: 'dinner',
    tags: ['Vegetarian', 'Gluten-Free'],
    avoidAllergens: ['Milk']
  }
]

/**
 * Filter meals based on user's dietary preferences and allergies.
 * 
 * @param {Array} meals - Array of meal objects
 * @param {Array} dietaryPrefs - User's dietary preferences (e.g., ['Vegetarian', 'Gluten-Free'])
 * @param {Array} allergies - User's allergies (e.g., ['Milk', 'Peanuts'])
 * @returns {Array} Filtered meals that match preferences and avoid allergens
 */
export function filterMealsForUser(meals, dietaryPrefs = [], allergies = []) {
  const dietarySet = new Set(dietaryPrefs.filter(p => p && p !== 'Everything'))
  const allergySet = new Set(allergies.filter(a => a && a !== 'None'))
  
  return meals.filter(meal => {
    // Check allergies first - exclude meals containing user's allergens
    for (const allergy of allergySet) {
      if (meal.avoidAllergens.includes(allergy)) {
        return false
      }
    }
    
    // If no dietary preferences (or only "Everything"), all non-allergen meals are compatible
    if (dietarySet.size === 0) {
      return true
    }
    
    // Check if meal has at least one matching dietary tag
    const mealTags = new Set(meal.tags)
    for (const pref of dietarySet) {
      if (mealTags.has(pref)) {
        return true
      }
    }
    
    return false
  })
}

/**
 * Generate a weekly meal plan based on user preferences.
 * 
 * Mirrors the server-side logic in meals/sample_plan_views.py:
 * 1. Try compatible meals that haven't been used yet
 * 2. Fall back to any unused meal (even if not compatible with dietary prefs)
 * 3. Fall back to all meals if everything has been used (allow repeats)
 * 
 * @param {Array} filteredMeals - Pre-filtered meals based on user preferences
 * @param {number} householdSize - Number of people in household
 * @returns {Object} Plan data with meals array and week summary
 */
export function generateWeeklyPlan(filteredMeals, householdSize = 1) {
  // Group filtered (compatible) meals by type
  const compatibleByType = {
    breakfast: filteredMeals.filter(m => m.meal_type === 'breakfast'),
    lunch: filteredMeals.filter(m => m.meal_type === 'lunch'),
    dinner: filteredMeals.filter(m => m.meal_type === 'dinner')
  }
  
  // Group ALL meals by type (for fallback when no compatible meals available)
  const allMealsByType = {
    breakfast: SAMPLE_MEALS.filter(m => m.meal_type === 'breakfast'),
    lunch: SAMPLE_MEALS.filter(m => m.meal_type === 'lunch'),
    dinner: SAMPLE_MEALS.filter(m => m.meal_type === 'dinner')
  }
  
  const meals = []
  const usedMealNames = new Set()  // Track by name to match server-side
  
  for (const day of DAYS_OF_WEEK) {
    for (const mealType of MEAL_TYPES) {
      const typeKey = mealType.toLowerCase()
      const compatibleMeals = compatibleByType[typeKey]
      const allMealsOfType = allMealsByType[typeKey]
      
      // Step 1: Try compatible meals that haven't been used
      let candidates = compatibleMeals.filter(m => !usedMealNames.has(m.name))
      
      // Step 2: Fall back to ANY unused meal (even if not compatible with dietary prefs)
      if (candidates.length === 0) {
        candidates = allMealsOfType.filter(m => !usedMealNames.has(m.name))
      }
      
      // Step 3: If all meals used, allow repeats from all meals
      if (candidates.length === 0) {
        candidates = allMealsOfType
      }
      
      // Select meal using deterministic index for consistency (matches server-side)
      const dayIndex = DAYS_OF_WEEK.indexOf(day)
      const typeIndex = MEAL_TYPES.indexOf(mealType)
      const mealIndex = (dayIndex + typeIndex) % candidates.length
      const selectedMeal = candidates[mealIndex]
      
      usedMealNames.add(selectedMeal.name)
      
      meals.push({
        day,
        meal_type: mealType,
        meal_name: selectedMeal.name,
        meal_description: selectedMeal.description,
        servings: householdSize
      })
    }
  }
  
  return {
    meals,
    week_summary: generateWeekSummary(householdSize, meals.length)
  }
}

/**
 * Generate a summary string for the meal plan.
 */
function generateWeekSummary(householdSize, mealCount) {
  const parts = []
  
  if (householdSize > 1) {
    parts.push(`Meals planned for ${householdSize} people`)
  }
  
  parts.push(`${mealCount} meals across 7 days`)
  parts.push('Balanced variety of breakfast, lunch, and dinner options')
  
  return parts.join('. ') + '.'
}

