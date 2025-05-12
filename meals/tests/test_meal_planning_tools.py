"""
Unit tests for meal planning tools.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from meals.models import Meal, MealPlan, MealPlanMeal
from meals.meal_planning_tools import (
    get_meal_macro_info,
    find_related_youtube_videos
)

User = get_user_model()

class TestMealPlanningTools(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Create a test meal
        self.meal = Meal.objects.create(
            name='Test Meal',
            description='This is a test meal',
            creator=self.user
        )
        
        # Create a test meal plan
        self.meal_plan = MealPlan.objects.create(
            user=self.user,
            week_start_date='2023-01-01',
            week_end_date='2023-01-07'
        )
        
        # Create a test meal plan meal
        self.meal_plan_meal = MealPlanMeal.objects.create(
            meal=self.meal,
            meal_plan=self.meal_plan,
            day='Monday',
            meal_type='Dinner'
        )

    @patch('meals.meal_planning_tools.get_meal_macro_information')
    def test_get_meal_macro_info_success(self, mock_get_macro_info):
        # Mock the return value of get_meal_macro_information
        macro_data = {
            "calories": 350.5,
            "protein": 25.2,
            "carbohydrates": 30.5,
            "fat": 12.3,
            "fiber": 5.2,
            "sugar": 3.1,
            "sodium": 120.0,
            "serving_size": "1 cup (240g)"
        }
        mock_get_macro_info.return_value = macro_data
        
        # Call the function
        result = get_meal_macro_info(self.meal.id)
        
        # Check the result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["macros"], macro_data)
        
        # Verify the mock was called with the correct arguments
        mock_get_macro_info.assert_called_once_with(
            meal_name=self.meal.name,
            meal_description=self.meal.description,
            ingredients=None
        )
    
    @patch('meals.meal_planning_tools.get_meal_macro_information')
    def test_get_meal_macro_info_failure(self, mock_get_macro_info):
        # Mock get_meal_macro_information returning None (failure)
        mock_get_macro_info.return_value = None
        
        # Call the function
        result = get_meal_macro_info(self.meal.id)
        
        # Check the result
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Macro lookup failed.")
    
    def test_get_meal_macro_info_invalid_meal(self):
        # Call the function with an invalid meal ID
        result = get_meal_macro_info(9999)
        
        # Check the result
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Meal 9999 not found.")

    @patch('meals.meal_planning_tools.find_youtube_cooking_videos')
    def test_find_related_youtube_videos_success(self, mock_find_videos):
        # Mock the return value of find_youtube_cooking_videos
        videos_data = {
            "videos": [
                {
                    "title": "Test Video 1",
                    "url": "https://www.youtube.com/watch?v=123",
                    "channel": "Test Channel",
                    "description": "Test Description",
                    "duration": "10:30",
                    "relevance_score": 9.5,
                    "relevance_explanation": "Very relevant",
                    "recommended": True,
                    "matching_ingredients": ["ingredient1", "ingredient2"],
                    "matching_techniques": ["technique1", "technique2"]
                }
            ],
            "search_query": "Test Meal recipe"
        }
        mock_find_videos.return_value = videos_data
        
        # Mock format_for_structured_output
        with patch('meals.meal_planning_tools.format_for_structured_output', return_value=videos_data) as mock_format:
            # Call the function
            result = find_related_youtube_videos(self.meal.id)
            
            # Check the result
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["videos"], videos_data)
            
            # Verify the mock was called with the correct arguments
            mock_find_videos.assert_called_once_with(
                meal_name=self.meal.name,
                meal_description=self.meal.description,
                limit=5
            )
            mock_format.assert_called_once_with(videos_data)
    
    def test_find_related_youtube_videos_invalid_meal(self):
        # Call the function with an invalid meal ID
        result = find_related_youtube_videos(9999)
        
        # Check the result
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Meal 9999 not found.")

    @patch('meals.meal_planning_tools.find_youtube_cooking_videos')
    def test_find_related_youtube_videos_with_max_results(self, mock_find_videos):
        # Mock the return value of find_youtube_cooking_videos
        videos_data = {"videos": [], "search_query": "Test Meal recipe"}
        mock_find_videos.return_value = videos_data
        
        # Mock format_for_structured_output
        with patch('meals.meal_planning_tools.format_for_structured_output', return_value=videos_data) as mock_format:
            # Call the function with max_results parameter
            find_related_youtube_videos(self.meal.id, max_results=10)
            
            # Verify the mock was called with the correct limit
            mock_find_videos.assert_called_once_with(
                meal_name=self.meal.name,
                meal_description=self.meal.description,
                limit=10
            ) 