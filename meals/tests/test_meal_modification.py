import json
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from meals.meal_modification_parser import parse_modification_request
from meals.meal_plan_service import apply_modifications
from meals.models import MealPlan, MealPlanMeal
from meals.pydantic_models import MealPlanModificationRequest, MealSlotDirective


class MockResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class MealPlanModificationTests(TestCase):
    
    def setUp(self):
        # Set up mock user and MealPlan
        self.user = MagicMock()
        self.meal_plan = MagicMock(spec=MealPlan)
        self.meal_plan_meal = MagicMock(spec=MealPlanMeal)
        self.meal_plan_meal.id = 1
        self.meal_plan_meal.meal.name = "Test Meal"
        self.meal_plan_meal.day = "Monday"
        self.meal_plan_meal.meal_type = "Dinner"
        
        # Set up meal_plan.mealplanmeal_set
        self.meal_plan.mealplanmeal_set.select_related.return_value.all.return_value = [self.meal_plan_meal]
        
    @patch('meals.meal_modification_parser.client.responses.create')
    def test_parse_modification_request(self, mock_create):
        # Prepare mock response
        sample_response = {
            "slots": [
                {
                    "meal_plan_meal_id": 1,
                    "meal_name": "Test Meal",
                    "change_rules": ["make it vegan", "no rice"]
                }
            ]
        }
        mock_create.return_value = MockResponse(json.dumps(sample_response))
        
        # Call the function
        result = parse_modification_request("Make Monday's dinner vegan with no rice", self.meal_plan)
        
        # Assert expectations
        self.assertIsInstance(result, MealPlanModificationRequest)
        self.assertEqual(len(result.slots), 1)
        self.assertEqual(result.slots[0].meal_plan_meal_id, 1)
        self.assertEqual(result.slots[0].meal_name, "Test Meal")
        self.assertEqual(result.slots[0].change_rules, ["make it vegan", "no rice"])
        
    @patch('meals.meal_plan_service.parse_modification_request')
    @patch('meals.meal_plan_service.modify_existing_meal_plan')
    @patch('meals.meal_plan_service.analyze_and_replace_meals')
    def test_apply_modifications(self, mock_analyze, mock_modify, mock_parse):
        # Prepare mock response from parser
        mock_directive = MealSlotDirective(
            meal_plan_meal_id=1,
            meal_name="Test Meal",
            change_rules=["make it vegan", "no rice"]
        )
        mock_request = MealPlanModificationRequest(slots=[mock_directive])
        mock_parse.return_value = mock_request
        
        # Mock the id_to_mpm dictionary
        self.meal_plan.mealplanmeal_set.select_related.return_value.all.return_value = [self.meal_plan_meal]
        
        # Call the function
        result = apply_modifications(self.user, self.meal_plan, "Make Monday's dinner vegan with no rice")
        
        # Assert expectations
        self.assertEqual(result, self.meal_plan)
        mock_modify.assert_called_once()
        mock_analyze.assert_called_once()
        
    @patch('meals.meal_plan_service.parse_modification_request')
    @patch('meals.meal_plan_service.modify_existing_meal_plan')
    @patch('meals.meal_plan_service.analyze_and_replace_meals')
    def test_apply_modifications_no_changes(self, mock_analyze, mock_modify, mock_parse):
        # Prepare mock response with empty change_rules
        mock_directive = MealSlotDirective(
            meal_plan_meal_id=1,
            meal_name="Test Meal",
            change_rules=[]
        )
        mock_request = MealPlanModificationRequest(slots=[mock_directive])
        mock_parse.return_value = mock_request
        
        # Mock the id_to_mpm dictionary
        self.meal_plan.mealplanmeal_set.select_related.return_value.all.return_value = [self.meal_plan_meal]
        
        # Call the function
        result = apply_modifications(self.user, self.meal_plan, "Some unrelated request")
        
        # Assert expectations
        self.assertEqual(result, self.meal_plan)
        mock_modify.assert_not_called()
        mock_analyze.assert_not_called()


if __name__ == '__main__':
    unittest.main() 