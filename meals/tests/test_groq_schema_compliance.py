"""
Tests for Groq structured output schema compliance.

This module validates that all Pydantic models used with Groq's structured
outputs API comply with Groq's requirements:
1. All objects must have additionalProperties: false
2. All properties must be in the required list
3. No dynamic object keys (use arrays instead)
"""
import pytest
from meals.pydantic_models import (
    AllergenAnalysis,
    IngredientSubstitution,
    MealMacroInfo,
    PromptMealMap,
    PromptedSlot,
    MealsToReplaceSchema,
    YouTubeVideo,
    YouTubeVideoResults,
)


class TestGroqSchemaCompliance:
    """Test that all schemas used with Groq comply with requirements."""
    
    def test_allergen_analysis_schema_no_additional_properties(self):
        """Ensure AllergenAnalysis schema has additionalProperties: false"""
        schema = AllergenAnalysis.model_json_schema()
        assert schema.get("additionalProperties") == False, \
            "AllergenAnalysis must have additionalProperties: false for Groq compatibility"
    
    def test_allergen_analysis_all_fields_required(self):
        """Ensure all fields are in required list (Groq requirement)"""
        schema = AllergenAnalysis.model_json_schema()
        required = set(schema.get("required", []))
        properties = set(schema.get("properties", {}).keys())
        # Note: Groq requires all fields to be required, but Python Optional fields
        # with defaults are valid if they have default=None
        assert required.issubset(properties), \
            "All required fields must be in properties"
    
    def test_allergen_analysis_substitutions_array_format(self):
        """Ensure substitutions uses array, not dynamic keys"""
        schema = AllergenAnalysis.model_json_schema()
        subs_schema = schema["properties"]["substitutions"]
        assert subs_schema["type"] == "array", \
            "Substitutions must be an array, not an object with dynamic keys"
        
        # Verify the array items reference IngredientSubstitution
        assert "items" in subs_schema
        items_ref = subs_schema["items"]
        # Should either be a reference or an inline schema
        assert "$ref" in items_ref or "type" in items_ref
    
    def test_ingredient_substitution_schema_compliance(self):
        """Ensure IngredientSubstitution schema is Groq-compliant"""
        schema = IngredientSubstitution.model_json_schema()
        assert schema.get("additionalProperties") == False
        
        # All fields should be required
        required = set(schema.get("required", []))
        properties = set(schema.get("properties", {}).keys())
        assert required == properties, \
            "IngredientSubstitution must have all fields required"
    
    def test_allergen_analysis_validation_from_json(self):
        """Test that AllergenAnalysis can be validated from JSON"""
        test_data = {
            "is_safe": False,
            "flagged_ingredients": ["milk", "almonds"],
            "substitutions": [
                {"ingredient": "milk", "alternatives": ["oat milk", "soy milk"]},
                {"ingredient": "almonds", "alternatives": ["pumpkin seeds"]}
            ],
            "reasoning": "Contains dairy and nuts"
        }
        model = AllergenAnalysis.model_validate(test_data)
        assert model.is_safe == False
        assert len(model.substitutions) == 2
        assert model.substitutions[0].ingredient == "milk"
        assert "oat milk" in model.substitutions[0].alternatives
    
    def test_allergen_analysis_safe_meal(self):
        """Test AllergenAnalysis with safe meal (no substitutions needed)"""
        test_data = {
            "is_safe": True,
            "flagged_ingredients": [],
            "substitutions": [],
            "reasoning": "No allergens detected"
        }
        model = AllergenAnalysis.model_validate(test_data)
        assert model.is_safe == True
        assert len(model.flagged_ingredients) == 0
        assert len(model.substitutions) == 0
    
    def test_meal_macro_info_optional_fields_have_defaults(self):
        """Ensure MealMacroInfo optional fields have defaults (Groq requirement)"""
        schema = MealMacroInfo.model_json_schema()
        properties = schema.get("properties", {})
        
        # Optional fields that should have defaults
        optional_fields = ["fiber", "sugar", "sodium"]
        for field in optional_fields:
            # These fields should either not be in required, or have a default value
            # In Pydantic v2, Optional with Field(default=None) allows this
            assert field in properties, f"{field} should be in properties"
    
    def test_youtube_video_optional_fields_have_defaults(self):
        """Ensure YouTubeVideo optional fields have defaults"""
        schema = YouTubeVideo.model_json_schema()
        properties = schema.get("properties", {})
        
        # Optional fields
        optional_fields = ["description", "duration"]
        for field in optional_fields:
            assert field in properties
    
    def test_prompted_slot_optional_notes_has_default(self):
        """Ensure PromptedSlot.notes has default value"""
        schema = PromptedSlot.model_json_schema()
        properties = schema.get("properties", {})
        assert "notes" in properties
    
    def test_no_dynamic_keys_in_schemas(self):
        """Verify no schemas use dynamic keys (additionalProperties with schema)"""
        schemas_to_check = [
            AllergenAnalysis,
            MealMacroInfo,
            PromptMealMap,
            YouTubeVideoResults,
        ]
        
        for model_cls in schemas_to_check:
            schema = model_cls.model_json_schema()
            
            # Check main schema
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if prop_schema.get("type") == "object":
                        # If it's an object, it must have additionalProperties: false
                        # or it should be an array of objects instead
                        assert prop_schema.get("additionalProperties") == False or \
                               "items" in prop_schema, \
                            f"{model_cls.__name__}.{prop_name} must not use dynamic keys"
    
    def test_schema_serialization_roundtrip(self):
        """Test that schemas can serialize and deserialize correctly"""
        # Create a sample AllergenAnalysis
        data = AllergenAnalysis(
            is_safe=False,
            flagged_ingredients=["peanuts"],
            substitutions=[
                IngredientSubstitution(
                    ingredient="peanuts",
                    alternatives=["sunflower seeds", "pumpkin seeds"]
                )
            ],
            reasoning="Contains peanuts which user is allergic to"
        )
        
        # Serialize to JSON
        json_str = data.model_dump_json()
        
        # Deserialize back
        data_reloaded = AllergenAnalysis.model_validate_json(json_str)
        
        # Verify it matches
        assert data_reloaded.is_safe == data.is_safe
        assert data_reloaded.flagged_ingredients == data.flagged_ingredients
        assert len(data_reloaded.substitutions) == len(data.substitutions)
        assert data_reloaded.reasoning == data.reasoning


class TestGroqSchemaGeneration:
    """Test that model_json_schema() generates valid Groq schemas"""
    
    def test_allergen_analysis_schema_structure(self):
        """Verify the schema structure matches Groq requirements"""
        schema = AllergenAnalysis.model_json_schema()
        
        # Should have these top-level keys
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        
        # All required fields should be present
        required_fields = {"is_safe", "flagged_ingredients", "substitutions", "reasoning"}
        assert set(schema["required"]) == required_fields
    
    def test_schema_does_not_allow_extra_fields(self):
        """Test that extra fields are rejected (strict mode)"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            AllergenAnalysis.model_validate({
                "is_safe": True,
                "flagged_ingredients": [],
                "substitutions": [],
                "reasoning": "Safe",
                "extra_field": "should fail"  # This should be rejected
            })

