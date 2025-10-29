import pytest

from meals.email_service import _iter_valid_shopping_items


def test_iter_valid_shopping_items_handles_non_dict_entries():
    items = [
        {"ingredient": "Apples", "category": "Produce"},
        "Plain string item",
        '{"ingredient": "Milk", "category": "Dairy"}',
        123,
        ["nested list"],
    ]

    normalized = list(_iter_valid_shopping_items(items))

    assert normalized == [
        {"ingredient": "Apples", "category": "Produce"},
        {"ingredient": "Milk", "category": "Dairy"},
    ]
