"""
Integration tests for allergen checking functionality.

Tests the check_meal_for_allergens_gpt function with mocked Groq responses
to ensure proper handling of allergen analysis and substitutions.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from meals.meal_plan_service import check_meal_for_allergens_gpt
from meals.models import Meal, MealAllergenSafety
from custom_auth.models import CustomUser
from meals.pydantic_models import AllergenAnalysis, IngredientSubstitution


@pytest.fixture
def sample_user(db):
    """Create a test user with allergies"""
    user = CustomUser.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    # Add allergies through user profile
    user.allergies = ["dairy", "nuts"]
    user.save()
    return user


@pytest.fixture
def sample_meal(db):
    """Create a test meal with ingredients"""
    meal = Meal.objects.create(
        name="Test Pasta",
        description="Creamy pasta with almonds"
    )
    return meal


@pytest.fixture
def chef_meal(db):
    """Create a test chef meal"""
    from chefs.models import Chef
    # Create a chef first
    chef = Chef.objects.create(
        user=CustomUser.objects.create_user(
            username="testchef",
            email="chef@example.com",
            password="chefpass123"
        ),
        bio="Test chef"
    )
    meal = Meal.objects.create(
        name="Chef's Special",
        description="Chef-created special dish",
        chef=chef
    )
    return meal


class TestAllergenCheckingWithGroq:
    """Test allergen checking with mocked Groq API responses"""
    
    @patch('meals.meal_plan_service._get_groq_client')
    @patch('meals.meal_plan_service.groq_call_with_retry')
    def test_unsafe_meal_with_substitutions(
        self, 
        mock_groq_retry, 
        mock_get_client,
        sample_user,
        sample_meal,
        db
    ):
        """Test identifying unsafe meal and providing substitutions"""
        # Setup mock Groq client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock Groq response
        response_data = {
            "is_safe": False,
            "flagged_ingredients": ["milk", "almonds"],
            "substitutions": [
                {
                    "ingredient": "milk",
                    "alternatives": ["oat milk", "soy milk"]
                },
                {
                    "ingredient": "almonds",
                    "alternatives": ["pumpkin seeds", "sunflower seeds"]
                }
            ],
            "reasoning": "Contains dairy (milk) and tree nuts (almonds)"
        }
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)
        mock_groq_retry.return_value = mock_response
        
        # Call the function
        result = check_meal_for_allergens_gpt(
            meal=sample_meal,
            user=sample_user,
            ingredients=["milk", "almonds", "pasta", "olive oil"]
        )
        
        # Verify results
        assert result["is_safe"] == False
        assert "milk" in result["flagged_ingredients"]
        assert "almonds" in result["flagged_ingredients"]
        assert "milk" in result["substitutions"]
        assert "oat milk" in result["substitutions"]["milk"]
        assert "almonds" in result["substitutions"]
        
        # Verify cache was created
        cache_entry = MealAllergenSafety.objects.filter(
            meal=sample_meal,
            user=sample_user
        ).first()
        assert cache_entry is not None
        assert cache_entry.is_safe == False
    
    @patch('meals.meal_plan_service._get_groq_client')
    @patch('meals.meal_plan_service.groq_call_with_retry')
    def test_safe_meal_no_allergens(
        self,
        mock_groq_retry,
        mock_get_client,
        sample_user,
        sample_meal,
        db
    ):
        """Test safe meal with no allergens"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        response_data = {
            "is_safe": True,
            "flagged_ingredients": [],
            "substitutions": [],
            "reasoning": "No allergens detected in the ingredients"
        }
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)
        mock_groq_retry.return_value = mock_response
        
        result = check_meal_for_allergens_gpt(
            meal=sample_meal,
            user=sample_user,
            ingredients=["pasta", "tomato sauce", "olive oil", "basil"]
        )
        
        assert result["is_safe"] == True
        assert len(result["flagged_ingredients"]) == 0
        assert len(result["substitutions"]) == 0
    
    @patch('meals.meal_plan_service._get_groq_client')
    @patch('meals.meal_plan_service.groq_call_with_retry')
    def test_chef_meal_no_substitutions_offered(
        self,
        mock_groq_retry,
        mock_get_client,
        sample_user,
        chef_meal,
        db
    ):
        """Test that chef meals don't offer substitutions even if unsafe"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        response_data = {
            "is_safe": False,
            "flagged_ingredients": ["milk"],
            "substitutions": [
                {
                    "ingredient": "milk",
                    "alternatives": ["oat milk", "soy milk"]
                }
            ],
            "reasoning": "Contains dairy"
        }
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_data)
        mock_groq_retry.return_value = mock_response
        
        result = check_meal_for_allergens_gpt(
            meal=chef_meal,
            user=sample_user,
            ingredients=["milk", "pasta"],
            is_chef=True
        )
        
        # Should be unsafe but no substitutions offered
        assert result["is_safe"] == False
        assert len(result["substitutions"]) == 0
        assert "Chef-created meal" in result["reasoning"]
    
    @patch('meals.meal_plan_service._get_groq_client')
    @patch('meals.meal_plan_service.groq_call_with_retry')
    def test_malformed_json_response_handling(
        self,
        mock_groq_retry,
        mock_get_client,
        sample_user,
        sample_meal,
        db
    ):
        """Test handling of malformed JSON response from Groq"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Return invalid JSON (missing comma at char 913, similar to original error)
        invalid_json = '{"is_safe": false, "flagged_ingredients": ["milk"] "substitutions": []}'
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = invalid_json
        mock_groq_retry.return_value = mock_response
        
        # Should handle gracefully with fallback
        result = check_meal_for_allergens_gpt(
            meal=sample_meal,
            user=sample_user,
            ingredients=["milk", "pasta"]
        )
        
        # Should return safe defaults (flagging as unsafe to be cautious)
        assert result["is_safe"] == False
        assert "Unable to parse" in result["reasoning"]
    
    @patch('meals.meal_plan_service._get_groq_client')
    def test_cached_result_returned(
        self,
        mock_get_client,
        sample_user,
        sample_meal,
        db
    ):
        """Test that cached results are returned without API call"""
        # Create a cached entry
        MealAllergenSafety.objects.create(
            meal=sample_meal,
            user=sample_user,
            is_safe=True,
            flagged_ingredients=[],
            substitutions={},
            reasoning="Previously checked and safe"
        )
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Call function
        result = check_meal_for_allergens_gpt(
            meal=sample_meal,
            user=sample_user,
            ingredients=["pasta"]
        )
        
        # Should use cached result
        assert result["is_safe"] == True
        assert result["reasoning"] == "Previously checked and safe"
        
        # Groq client should not be called
        mock_get_client.assert_not_called()
    
    @patch('meals.meal_plan_service._get_groq_client')
    @patch('meals.meal_plan_service.get_openai_client')
    def test_fallback_to_openai_when_no_groq(
        self,
        mock_openai_client,
        mock_get_groq_client,
        sample_user,
        sample_meal,
        db
    ):
        """Test fallback to OpenAI when Groq is not available"""
        # Groq not available
        mock_get_groq_client.return_value = None
        
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_client.return_value = mock_client
        
        response_data = {
            "is_safe": True,
            "flagged_ingredients": [],
            "substitutions": [],
            "reasoning": "No allergens"
        }
        
        mock_response = MagicMock()
        mock_response.output_text = json.dumps(response_data)
        mock_client.responses.create.return_value = mock_response
        
        result = check_meal_for_allergens_gpt(
            meal=sample_meal,
            user=sample_user,
            ingredients=["pasta"]
        )
        
        assert result["is_safe"] == True
        # Verify OpenAI was called
        mock_client.responses.create.assert_called_once()


class TestAllergenAnalysisModel:
    """Test the AllergenAnalysis Pydantic model directly"""
    
    def test_model_validation_with_valid_data(self):
        """Test model validates correctly with valid data"""
        data = {
            "is_safe": False,
            "flagged_ingredients": ["peanuts", "shellfish"],
            "substitutions": [
                {
                    "ingredient": "peanuts",
                    "alternatives": ["sunflower butter", "tahini"]
                },
                {
                    "ingredient": "shellfish",
                    "alternatives": ["chicken", "tofu"]
                }
            ],
            "reasoning": "Contains allergens"
        }
        
        model = AllergenAnalysis.model_validate(data)
        assert model.is_safe == False
        assert len(model.flagged_ingredients) == 2
        assert len(model.substitutions) == 2
    
    def test_model_rejects_extra_fields(self):
        """Test model rejects extra fields (strict mode)"""
        data = {
            "is_safe": True,
            "flagged_ingredients": [],
            "substitutions": [],
            "reasoning": "Safe",
            "extra_field": "not allowed"
        }
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            AllergenAnalysis.model_validate(data)
    
    def test_model_requires_all_fields(self):
        """Test model requires all fields"""
        data = {
            "is_safe": True,
            "flagged_ingredients": []
            # Missing substitutions and reasoning
        }
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            AllergenAnalysis.model_validate(data)
    
    def test_substitutions_array_format(self):
        """Test substitutions are in array format, not dict"""
        data = {
            "is_safe": False,
            "flagged_ingredients": ["milk"],
            "substitutions": [
                {
                    "ingredient": "milk",
                    "alternatives": ["oat milk"]
                }
            ],
            "reasoning": "Has dairy"
        }
        
        model = AllergenAnalysis.model_validate(data)
        assert isinstance(model.substitutions, list)
        assert hasattr(model.substitutions[0], 'ingredient')
        assert hasattr(model.substitutions[0], 'alternatives')

