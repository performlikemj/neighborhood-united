# Meal Plan Modification System

This document outlines the meal plan modification system, which allows users to make specific changes to their meal plans using natural language prompts.

## Overview

The meal plan modification system parses free-form text requests and intelligently identifies which meals in a plan should be modified based on the user's directives. This system is designed to handle a variety of change requests, from simple meal swaps to more complex dietary modifications across multiple days.

## Components

1. **Pydantic Models** (`pydantic_models.py`)
   - `MealSlotDirective`: Represents instructions for a single meal slot, identified by its `meal_plan_meal_id`
   - `MealPlanModificationRequest`: Contains a list of slot directives

2. **Parser** (`meal_modification_parser.py`) 
   - Converts free-form user prompts into structured directives
   - Uses OpenAI's Responses API with JSON Schema validation
   - Maps user requests to specific meal slots in the plan

3. **Executor** (`meal_plan_service.py`)
   - The `apply_modifications` function processes the parsed directives
   - Calls `modify_existing_meal_plan` for each slot that needs changes
   - Optimizes by running `analyze_and_replace_meals` only once after all changes

4. **API Endpoint** (`views.py`)
   - `api_modify_meal_plan`: REST API endpoint to modify a meal plan using a text prompt

## Usage

### API Endpoint

```
POST /api/modify_meal_plan/{meal_plan_id}/
```

Request body:
```json
{
  "prompt": "Make all the dinners vegan and replace Tuesday's lunch with something spicy"
}
```

Response:
```json
{
  "status": "success",
  "message": "Meal plan updated successfully",
  "meal_plan_id": 123,
  "meals": [
    {
      "id": 456,
      "day": "Monday",
      "meal_type": "Breakfast",
      "meal_name": "Avocado Toast",
      "meal_description": "Creamy avocado on whole grain toast",
      "is_chef_meal": false
    },
    {
      "id": 529,
      "day" "Tuesday",
      "meal_type": "Lunch",
      "meal_name": "Jalapeño Citrus Salmon",
      "meal_description": "Spicy salmon with spicy and zesty citrust-jalapeño sauce",
      "is_chef_meal": false
    }
    ...
  ]
}
```

### Example Prompts

- "Make all dinners vegan"
- "Replace Tuesday's lunch with pasta"
- "Add more protein to my Wednesday breakfast"
- "I don't want rice in any of my meals"
- "Make Saturday's dinner gluten-free"

## Edge Cases

- **Ambiguous requests**: The parser distributes rules to all applicable slots
- **Empty requests**: Results in no changes (all `change_rules` arrays empty)
- **Invalid meal_plan_meal_id**: Caught and logged as a warning
- **Multiple rule types**: Stored as separate items in the `change_rules` array

## Testing

Unit tests are provided in `tests/test_meal_modification.py` and cover:
- Parsing the user's request into structured directives
- Applying the modifications to the meal plan
- Handling edge cases such as empty requests 

## Meal Macro Information & YouTube Video Tools

### get_meal_macro_info

This tool provides nutritional information for a specific meal, using OpenAI to generate accurate macro estimates.

```
POST /api/meal_planning/get_meal_macro_info/
```

Request body:
```json
{
  "meal_id": 123
}
```

Response:
```json
{
  "status": "success",
  "macros": {
    "calories": 350.5,
    "protein": 25.2,
    "carbohydrates": 30.5,
    "fat": 12.3,
    "fiber": 5.2,
    "sugar": 3.1,
    "sodium": 120.0,
    "serving_size": "1 cup (240g)"
  }
}
```

Features:
- Results are cached in the meal's `macro_info` JSON field for performance
- Validates data against `MealMacroInfo` schema before returning
- Provides comprehensive nutrient data including calories, macronutrients, and micronutrients

### find_related_youtube_videos

This tool finds and ranks relevant YouTube cooking videos for a specific meal, providing users with instructional content.

```
POST /api/meal_planning/find_related_youtube_videos/
```

Request body:
```json
{
  "meal_id": 123,
  "max_results": 5
}
```

Response:
```json
{
  "status": "success",
  "videos": {
    "ranked_videos": [
      {
        "video_id": "abcd1234",
        "relevance_score": 9.5,
        "relevance_explanation": "Directly matches the meal name and includes all key ingredients",
        "matching_ingredients": ["chicken", "broccoli", "garlic"],
        "matching_techniques": ["stir-frying", "marinating"],
        "recommended": true
      },
      ...
    ]
  }
}
```

Features:
- Results are cached in the meal's `youtube_videos` JSON field for performance
- Limits API requests to respect YouTube API quotas
- Uses OpenAI to intelligently rank videos by relevance to the specific meal
- Supports limiting the number of results (default 5, maximum 10)
- Identifies matching ingredients and cooking techniques

## Rate Limiting & Security

Both tools implement:
- Content hash caching to prevent duplicate OpenAI charges
- Proper error handling and logging
- Schema validation to prevent LLM hallucinations
- No storage of personal data or video thumbnails server-side 