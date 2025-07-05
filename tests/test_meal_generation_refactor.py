import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from custom_auth.models import CustomUser
from meals.models import MealPlan, PantryItem, DietaryPreference
from meals.meal_generation import generate_meal_details
from meals.pydantic_models import MealOutputSchema
from shared.utils import get_openai_client


class TestMealGenerationRefactor(TestCase):
    """
    Test suite for the refactored meal generation functionality.
    
    Tests cover:
    1. Unit test with dummy user and no expiring items
    2. Retry loop simulation with network failure
    3. Pydantic validation of GPT output
    """
    
    def setUp(self):
        """Set up test data."""
        # Create a dummy user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            household_member_count=2
        )
        
        # Create dietary preferences
        self.vegan_pref = DietaryPreference.objects.create(name='Vegan')
        self.user.dietary_preferences.add(self.vegan_pref)
        
        # Create meal plan
        self.meal_plan = MealPlan.objects.create(
            user=self.user,
            week_start_date=date.today(),
            week_end_date=date.today() + timedelta(days=6),
            is_approved=False,
            has_changes=False
        )
        
        # Mock OpenAI response data
        self.mock_gpt_response = {
            "meal": {
                "name": "Test Veggie Scramble",
                "description": "A delicious vegetable scramble perfect for breakfast",
                "dietary_preferences": ["Vegan"],
                "meal_type": "Breakfast",
                "is_chef_meal": False,
                "chef_name": None,
                "chef_meal_event_id": None,
                "used_pantry_items": []
            },
            "status": "success",
            "message": "Meal generated successfully",
            "current_time": "2024-01-15T10:00:00Z"
        }
        
        # Mock OpenAI response with pantry items
        self.mock_gpt_response_with_pantry = {
            "meal": {
                "name": "Test Pantry Meal",
                "description": "A meal using expiring pantry items",
                "dietary_preferences": ["Vegan"],
                "meal_type": "Dinner",
                "is_chef_meal": False,
                "chef_name": None,
                "chef_meal_event_id": None,
                "used_pantry_items": ["canned_beans", "rice"]
            },
            "status": "success",
            "message": "Meal generated successfully",
            "current_time": "2024-01-15T10:00:00Z"
        }

    @patch('meals.meal_generation.get_openai_client')
    @patch('meals.meal_generation.get_expiring_pantry_items')
    @patch('meals.meal_generation.compute_effective_available_items')
    @patch('meals.meal_generation.get_embedding')
    def test_unit_test_no_expiring_items(self, mock_get_embedding, mock_compute_effective, 
                                       mock_get_expiring, mock_get_client):
        """
        Test 1: Unit test with dummy user and no expiring items.
        GPT should legally return used_pantry_items: []
        """
        # Mock no expiring pantry items
        mock_get_expiring.return_value = []
        mock_compute_effective.return_value = {}
        mock_get_embedding.return_value = [0.1] * 1536  # Mock embedding
        
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.output_text = json.dumps(self.mock_gpt_response)
        mock_client.responses.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        # Test parameters
        meal_type = "Breakfast"
        existing_meal_names = set()
        existing_meal_embeddings = []
        
        # Call the function
        result = generate_meal_details(
            user=self.user,
            meal_type=meal_type,
            existing_meal_names=existing_meal_names,
            existing_meal_embeddings=existing_meal_embeddings,
            meal_plan=self.meal_plan,
            request_id="test-request-1"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], "Test Veggie Scramble")
        self.assertEqual(result['description'], "A delicious vegetable scramble perfect for breakfast")
        self.assertEqual(result['dietary_preferences'], ["Vegan"])
        self.assertEqual(result['used_pantry_items'], [])
        self.assertIn('meal_embedding', result)
        
        # Verify OpenAI was called with correct parameters
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args
        
        # Check that the prompt mentions no expiring items
        user_content = call_args[1]['input'][1]['content']
        self.assertIn("expiring pantry items: None", user_content)
        
        print("✅ Test 1 PASSED: No expiring items handled correctly")

    @patch('meals.meal_generation.get_openai_client')
    @patch('meals.meal_generation.get_expiring_pantry_items')
    @patch('meals.meal_generation.compute_effective_available_items')
    @patch('meals.meal_generation.get_embedding')
    def test_retry_loop_network_failure(self, mock_get_embedding, mock_compute_effective,
                                      mock_get_expiring, mock_get_client):
        """
        Test 2: Retry loop simulation with network failure.
        Verify second attempt runs and prompt length stays constant.
        """
        # Mock no expiring pantry items
        mock_get_expiring.return_value = []
        mock_compute_effective.return_value = {}
        mock_get_embedding.return_value = [0.1] * 1536  # Mock embedding
        
        # Mock OpenAI client with first call failing, second succeeding
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # First call raises network error, second succeeds
        mock_success_response = Mock()
        mock_success_response.output_text = json.dumps(self.mock_gpt_response)
        
        mock_client.responses.create.side_effect = [
            Exception("Network timeout"),  # First attempt fails
            mock_success_response          # Second attempt succeeds
        ]
        
        # Test parameters
        meal_type = "Lunch"
        existing_meal_names = set()
        existing_meal_embeddings = []
        
        # Call the function
        result = generate_meal_details(
            user=self.user,
            meal_type=meal_type,
            existing_meal_names=existing_meal_names,
            existing_meal_embeddings=existing_meal_embeddings,
            meal_plan=self.meal_plan,
            max_attempts=3,
            request_id="test-request-2"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], "Test Veggie Scramble")
        
        # Verify OpenAI was called twice (first failed, second succeeded)
        self.assertEqual(mock_client.responses.create.call_count, 2)
        
        # Check that prompt length is consistent between attempts
        first_call_args = mock_client.responses.create.call_args_list[0]
        second_call_args = mock_client.responses.create.call_args_list[1]
        
        first_prompt = first_call_args[1]['input'][1]['content']
        second_prompt = second_call_args[1]['input'][1]['content']
        
        # Prompt length should be the same (indicating consistent state)
        self.assertEqual(len(first_prompt), len(second_prompt))
        
        # Both prompts should contain the same key information
        for prompt in [first_prompt, second_prompt]:
            self.assertIn("expiring pantry items: None", prompt)
            self.assertIn("Meal type required: Lunch", prompt)
            self.assertIn("Household:", prompt)
        
        print("✅ Test 2 PASSED: Retry loop with network failure handled correctly")

    def test_pydantic_validation_success(self):
        """
        Test 3: Pydantic validation of GPT output.
        Feed GPT output into MealOutputSchema.model_validate_json() - no errors.
        """
        # Test with valid JSON
        valid_json = json.dumps(self.mock_gpt_response)
        
        # This should not raise any exceptions
        try:
            validated_data = MealOutputSchema.model_validate_json(valid_json)
            
            # Verify the data structure
            self.assertEqual(validated_data.meal.name, "Test Veggie Scramble")
            self.assertEqual(validated_data.meal.description, "A delicious vegetable scramble perfect for breakfast")
            self.assertEqual(validated_data.meal.dietary_preferences, ["Vegan"])
            self.assertEqual(validated_data.meal.used_pantry_items, [])
            self.assertEqual(validated_data.status, "success")
            self.assertFalse(validated_data.meal.is_chef_meal)
            self.assertIsNone(validated_data.meal.chef_name)
            self.assertIsNone(validated_data.meal.chef_meal_event_id)
            
            print("✅ Test 3a PASSED: Pydantic validation successful for valid JSON")
            
        except Exception as e:
            self.fail(f"Pydantic validation failed unexpectedly: {e}")

    def test_pydantic_validation_with_pantry_items(self):
        """
        Test 3b: Pydantic validation with pantry items.
        """
        # Test with pantry items
        pantry_json = json.dumps(self.mock_gpt_response_with_pantry)
        
        try:
            validated_data = MealOutputSchema.model_validate_json(pantry_json)
            
            # Verify pantry items are handled correctly
            self.assertEqual(validated_data.meal.used_pantry_items, ["canned_beans", "rice"])
            self.assertEqual(validated_data.meal.name, "Test Pantry Meal")
            
            print("✅ Test 3b PASSED: Pydantic validation with pantry items successful")
            
        except Exception as e:
            self.fail(f"Pydantic validation with pantry items failed: {e}")

    def test_pydantic_validation_invalid_json(self):
        """
        Test 3c: Pydantic validation with invalid JSON should raise appropriate errors.
        """
        # Test with invalid JSON structure
        invalid_json = json.dumps({
            "meal": {
                "name": "Test Meal",
                # Missing required fields
            },
            "status": "success"
        })
        
        with self.assertRaises(Exception):
            MealOutputSchema.model_validate_json(invalid_json)
            
        print("✅ Test 3c PASSED: Pydantic validation correctly rejects invalid JSON")

    @patch('meals.meal_generation.get_openai_client')
    @patch('meals.meal_generation.get_expiring_pantry_items')
    @patch('meals.meal_generation.compute_effective_available_items')
    @patch('meals.meal_generation.get_embedding')
    def test_integration_with_pantry_items(self, mock_get_embedding, mock_compute_effective,
                                         mock_get_expiring, mock_get_client):
        """
        Integration test: Test with actual pantry items to ensure used_pantry_items is populated correctly.
        """
        # Create pantry items
        pantry_item1 = PantryItem.objects.create(
            user=self.user,
            item_name="canned_beans",
            quantity=2,
            expiration_date=date.today() + timedelta(days=2)
        )
        pantry_item2 = PantryItem.objects.create(
            user=self.user,
            item_name="rice",
            quantity=1,
            expiration_date=date.today() + timedelta(days=3)
        )
        
        # Mock expiring pantry items
        mock_get_expiring.return_value = [
            {"item_id": pantry_item1.id, "item_name": "canned_beans", "quantity": 2},
            {"item_id": pantry_item2.id, "item_name": "rice", "quantity": 1}
        ]
        mock_compute_effective.return_value = {
            pantry_item1.id: (2, "cans"),
            pantry_item2.id: (1, "lb")
        }
        mock_get_embedding.return_value = [0.1] * 1536
        
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.output_text = json.dumps(self.mock_gpt_response_with_pantry)
        mock_client.responses.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        # Call the function
        result = generate_meal_details(
            user=self.user,
            meal_type="Dinner",
            existing_meal_names=set(),
            existing_meal_embeddings=[],
            meal_plan=self.meal_plan,
            request_id="test-request-4"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['used_pantry_items'], ["canned_beans", "rice"])
        
        # Verify prompt includes expiring items
        call_args = mock_client.responses.create.call_args
        user_content = call_args[1]['input'][1]['content']
        self.assertIn("canned_beans, rice", user_content)
        
        print("✅ Integration test PASSED: Pantry items handled correctly in meal generation")

    def run_all_tests(self):
        """
        Run all tests in sequence for quick smoke testing.
        """
        print("\n🚀 Running Meal Generation Refactor Smoke Tests...")
        print("=" * 60)
        
        try:
            self.test_unit_test_no_expiring_items()
            self.test_retry_loop_network_failure()
            self.test_pydantic_validation_success()
            self.test_pydantic_validation_with_pantry_items()
            self.test_pydantic_validation_invalid_json()
            self.test_integration_with_pantry_items()
            
            print("\n" + "=" * 60)
            print("🎉 ALL TESTS PASSED! Your refactoring is working correctly.")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise


# Standalone test runner for quick testing
if __name__ == "__main__":
    import django
    import os
    import sys
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')
    django.setup()
    
    # Run the tests
    test_instance = TestMealGenerationRefactor()
    test_instance.setUp()
    test_instance.run_all_tests() 