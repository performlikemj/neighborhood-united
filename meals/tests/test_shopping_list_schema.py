from meals.pydantic_models import ShoppingList


def test_shopping_list_schema_meal_names():
    data = {
        "items": [
            {
                "meal_names": ["Meal A", "Meal B"],
                "ingredient": "Tomato",
                "quantity": 3,
                "unit": "pieces",
                "notes": None,
                "category": "vegetables",
            }
        ]
    }
    result = ShoppingList.model_validate(data)
    assert result.items[0].meal_names == ["Meal A", "Meal B"]
