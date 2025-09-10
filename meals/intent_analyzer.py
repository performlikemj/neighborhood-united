"""
Intent Analysis System for Email Processing

This module implements intelligent intent analysis using the OpenAI Responses API
to determine user intent and predict which tools will be needed for the response.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field, ConfigDict
from openai import OpenAI
try:
    from groq import Groq  # optional Groq client for inference
except Exception:
    Groq = None
from django.conf import settings
import os
import re

logger = logging.getLogger(__name__)

# Control character regex for JSON sanitization  
CTRL_CHARS = re.compile(r'[\x00-\x1F]')

def _safe_load_and_validate(model_cls, raw: str):
    """
    Load JSON from OpenAI output_text, sanitising control chars once if needed.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = CTRL_CHARS.sub(
            lambda m: '\\u%04x' % ord(m.group()), raw
        )
        data = json.loads(cleaned)
    return model_cls.model_validate(data)

# Intent Classification Schema
class EmailIntent(BaseModel):
    """Structured output for email intent analysis"""
    model_config = ConfigDict(extra="forbid")
    
    primary_intent: Literal[
        "meal_planning", "shopping", "recipe_request", "nutrition_info", 
        "chef_connection", "payment_order", "dietary_preferences", 
        "pantry_management", "general_question"
    ] = Field(..., description="Primary intent category of the email")
    
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence score for the intent classification"
    )
    
    predicted_tools: List[str] = Field(
        ..., 
        description="List of tool names likely to be used in the response"
    )
    
    content_structure: Literal["simple", "structured", "complex"] = Field(
        ..., 
        description="Expected complexity of the response content"
    )
    
    requires_data_visualization: bool = Field(
        ..., 
        description="Whether the response will need tables, charts, or structured data display"
    )
    
    user_action_required: bool = Field(
        ..., 
        description="Whether the user needs to take action (approve, pay, etc.)"
    )
    
    urgency_level: Literal["low", "medium", "high"] = Field(
        ..., 
        description="Urgency level of the request"
    )
    
    key_entities: List[str] = Field(
        ..., 
        description="Important entities mentioned (meal names, dates, chef names, etc.)"
    )
    
    suggested_response_tone: Literal["informational", "promotional", "urgent", "friendly"] = Field(
        ..., 
        description="Recommended tone for the response"
    )

class IntentAnalysisResult:
    """Container for intent analysis results with additional metadata"""
    
    def __init__(self, intent: EmailIntent, raw_email: str, processing_time: float):
        self.intent = intent
        self.raw_email = raw_email
        self.processing_time = processing_time
        self.analysis_timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging"""
        return {
            "intent": self.intent.model_dump(),
            "raw_email_preview": self.raw_email[:200] + "..." if len(self.raw_email) > 200 else self.raw_email,
            "processing_time": self.processing_time,
            "analysis_timestamp": self.analysis_timestamp
        }

class EmailIntentAnalyzer:
    """
    Analyzes email content to determine user intent and predict required tools
    """
    
    # Tool prediction mappings based on intent categories
    INTENT_TOOL_MAPPINGS = {
        "meal_planning": [
            "create_meal_plan", "get_meal_plan", "list_user_meal_plans", 
            "modify_meal_plan", "list_upcoming_meals", "get_meal_plan_meals_info"
        ],
        "shopping": [
            "generate_shopping_list", "generate_instacart_link_tool", 
            "find_nearby_supermarkets", "check_pantry_items", "get_expiring_items"
        ],
        "recipe_request": [
            "email_generate_meal_instructions", "stream_meal_instructions", 
            "get_meal_details", "find_related_youtube_videos", "get_meal_macro_info"
        ],
        "nutrition_info": [
            "get_meal_macro_info", "check_meal_compatibility", 
            "list_dietary_preferences", "check_allergy_alert"
        ],
        "chef_connection": [
            "find_local_chefs", "get_chef_details", "view_chef_meal_events", 
            "place_chef_meal_event_order", "replace_meal_plan_meal"
        ],
        "payment_order": [
            "generate_payment_link", "check_payment_status", "get_order_details", 
            "cancel_order", "process_refund"
        ],
        "dietary_preferences": [
            "manage_dietary_preferences", "check_meal_compatibility", 
            "suggest_alternatives", "list_dietary_preferences"
        ],
        "pantry_management": [
            "check_pantry_items", "add_pantry_item", "get_expiring_items", 
            "determine_items_to_replenish", "set_emergency_supply_goal"
        ],
        "general_question": [
            "get_user_info", "get_current_date", "update_user_info"
        ]
    }
    
    # Keywords that help identify intent categories
    INTENT_KEYWORDS = {
        "meal_planning": [
            "meal plan", "weekly plan", "plan my meals", "create plan", 
            "this week", "next week", "meal schedule", "weekly menu"
        ],
        "shopping": [
            "shopping list", "grocery list", "buy", "purchase", "instacart", 
            "store", "supermarket", "ingredients needed"
        ],
        "recipe_request": [
            "recipe", "how to cook", "instructions", "how to make", 
            "cooking steps", "preparation", "tutorial", "video"
        ],
        "nutrition_info": [
            "nutrition", "calories", "macros", "protein", "carbs", "fat", 
            "healthy", "nutritional", "diet info"
        ],
        "chef_connection": [
            "chef", "local chef", "chef meal", "chef event", "order from chef", 
            "chef-made", "professional chef", "chef cooking"
        ],
        "payment_order": [
            "pay", "payment", "order", "checkout", "bill", "invoice", 
            "refund", "cancel order", "payment status"
        ],
        "dietary_preferences": [
            "dietary", "allergies", "vegan", "vegetarian", "gluten-free", 
            "preferences", "restrictions", "diet type"
        ],
        "pantry_management": [
            "pantry", "expiring", "expired", "inventory", "pantry items", 
            "stock", "supplies", "emergency supply"
        ]
    }
    
    def __init__(self, openai_client: OpenAI, groq_client: Optional[Any] = None):
        self.client = openai_client
        # Prefer provided groq client; else lazily create from settings/env
        if groq_client is not None:
            self.groq = groq_client
        else:
            try:
                api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
                self.groq = Groq(api_key=api_key) if (api_key and Groq is not None) else None
            except Exception:
                self.groq = None
    
    def analyze_intent(self, email_content: str, user_context: Optional[Dict] = None) -> IntentAnalysisResult:
        """
        Analyze email content to determine user intent and predict tools
        
        Args:
            email_content: The raw email content to analyze
            user_context: Optional user context for better analysis
            
        Returns:
            IntentAnalysisResult containing the analysis
        """
        import time
        start_time = time.time()
        
        try:
            # Pre-process email content
            cleaned_content = self._preprocess_email(email_content)
            
            # Get intent analysis from OpenAI
            intent = self._get_intent_from_openai(cleaned_content, user_context)
            
            # Post-process and validate
            validated_intent = self._validate_and_enhance_intent(intent, cleaned_content)
            
            processing_time = time.time() - start_time
            
            result = IntentAnalysisResult(
                intent=validated_intent,
                raw_email=email_content,
                processing_time=processing_time
            )
            
            logger.info(f"Intent analysis completed: {validated_intent.primary_intent} "
                       f"(confidence: {validated_intent.confidence:.2f}, "
                       f"tools: {len(validated_intent.predicted_tools)}, "
                       f"time: {processing_time:.2f}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in intent analysis: {str(e)}")
            # Return fallback intent
            fallback_intent = self._create_fallback_intent(email_content)
            processing_time = time.time() - start_time
            
            return IntentAnalysisResult(
                intent=fallback_intent,
                raw_email=email_content,
                processing_time=processing_time
            )
    
    def _preprocess_email(self, email_content: str) -> str:
        """Clean and prepare email content for analysis"""
        # Remove email headers, signatures, and formatting
        cleaned = re.sub(r'^(From:|To:|Subject:|Date:).*$', '', email_content, flags=re.MULTILINE)
        cleaned = re.sub(r'--+', '', cleaned)  # Remove signature separators
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
        cleaned = cleaned.strip()
        
        # Limit length for API efficiency
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000] + "..."
        
        return cleaned
    
    def _get_intent_from_openai(self, email_content: str, user_context: Optional[Dict] = None) -> EmailIntent:
        """Get intent analysis using Groq when available, else OpenAI Responses."""
        
        system_prompt = """You are an expert email intent analyzer for a meal planning assistant service.

Your task is to analyze incoming emails and determine:
1. The user's primary intent
2. Which tools will likely be needed to respond
3. The complexity and structure of the expected response
4. Whether the user needs to take action

INTENT CATEGORIES:
- meal_planning: Creating, viewing, or modifying meal plans
- shopping: Generating shopping lists, finding stores, Instacart links
- recipe_request: Asking for cooking instructions, recipes, or tutorials
- nutrition_info: Questions about calories, macros, nutritional content
- chef_connection: Finding local chefs, viewing chef meals, placing orders
- payment_order: Payment processing, order status, refunds
- dietary_preferences: Managing dietary restrictions, allergies, preferences
- pantry_management: Managing pantry items, expiring items, inventory
- general_question: General inquiries, account info, dates

ANALYSIS GUIDELINES:
- Be precise with intent classification
- Predict tools that will actually be used, not just related ones
- Consider user context if provided
- Assess complexity based on expected response elements
- Identify key entities (meal names, dates, chef names, etc.)
- Determine appropriate response tone

Return structured analysis following the EmailIntent schema."""

        user_prompt = f"""Analyze this email content for intent:

EMAIL CONTENT:
{email_content}

USER CONTEXT:
{self._serialize_user_context_safely(user_context) if user_context else "No additional context provided"}

Provide detailed intent analysis following the EmailIntent schema."""

        try:
            # Clean schema for OpenAI compatibility
            schema = self._clean_schema_for_openai(EmailIntent.model_json_schema())
            
            # Prefer Groq structured output if configured
            if getattr(self, 'groq', None):
                groq_resp = self.groq.chat.completions.create(
                    model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    top_p=1,
                    stream=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "email_intent",
                            "schema": schema,
                        },
                    },
                )
                content = groq_resp.choices[0].message.content or "{}"
                intent = _safe_load_and_validate(EmailIntent, content)
            else:
                response = self.client.responses.create(
                    model="gpt-5-mini",
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=False,
                    text={
                        "format": {
                            'type': 'json_schema',
                            'name': 'email_intent',
                            'schema': schema
                        }
                    }
                )
                
                # Parse and validate the response
                intent = _safe_load_and_validate(EmailIntent, response.output_text)
            return intent
            
        except Exception as e:
            logger.error(f"Error getting intent from OpenAI: {str(e)}")
            raise
    
    def _validate_and_enhance_intent(self, intent: EmailIntent, email_content: str) -> EmailIntent:
        """Validate and enhance the intent analysis with rule-based checks"""
        
        # Validate predicted tools exist in our tool registry
        from .tool_registration import TOOL_FUNCTION_MAP
        valid_tools = [tool for tool in intent.predicted_tools if tool in TOOL_FUNCTION_MAP]
        
        # Add tools based on keyword matching if OpenAI missed obvious ones
        detected_intent = self._detect_intent_by_keywords(email_content)
        if detected_intent and detected_intent in self.INTENT_TOOL_MAPPINGS:
            suggested_tools = self.INTENT_TOOL_MAPPINGS[detected_intent]
            for tool in suggested_tools[:3]:  # Add up to 3 additional tools
                if tool not in valid_tools and tool in TOOL_FUNCTION_MAP:
                    valid_tools.append(tool)
        
        # Ensure we have at least one tool predicted
        if not valid_tools:
            # Fallback to general tools
            valid_tools = ["get_user_info", "get_current_date"]
        
        # Update the intent with validated tools
        intent.predicted_tools = valid_tools
        
        # Adjust confidence based on keyword matching
        if detected_intent == intent.primary_intent:
            intent.confidence = min(1.0, intent.confidence + 0.1)
        
        return intent
    
    def _detect_intent_by_keywords(self, email_content: str) -> Optional[str]:
        """Detect intent using keyword matching as a fallback/validation method"""
        email_lower = email_content.lower()
        
        intent_scores = {}
        for intent_category, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in email_lower)
            if score > 0:
                intent_scores[intent_category] = score
        
        if intent_scores:
            return max(intent_scores, key=intent_scores.get)
        
        return None
    
    def _create_fallback_intent(self, email_content: str) -> EmailIntent:
        """Create a fallback intent when analysis fails"""
        
        # Try keyword-based detection
        detected_intent = self._detect_intent_by_keywords(email_content)
        primary_intent = detected_intent if detected_intent else "general_question"
        
        # Get basic tool predictions
        predicted_tools = self.INTENT_TOOL_MAPPINGS.get(primary_intent, ["get_user_info"])
        
        return EmailIntent(
            primary_intent=primary_intent,
            confidence=0.5,  # Low confidence for fallback
            predicted_tools=predicted_tools[:3],  # Limit to 3 tools
            content_structure="simple",
            requires_data_visualization=primary_intent in ["meal_planning", "shopping", "nutrition_info"],
            user_action_required=primary_intent in ["payment_order", "chef_connection"],
            urgency_level="medium",
            key_entities=[],
            suggested_response_tone="friendly"
        )
    
    def _serialize_user_context_safely(self, user_context: Dict) -> str:
        """Safely serialize user context, handling Django objects"""
        try:
            def convert_django_objects(obj):
                """Recursively convert Django objects to JSON-serializable types"""
                if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                    # Handle Django QuerySets and ManyRelatedManagers
                    if hasattr(obj, 'all'):
                        # This is likely a QuerySet or ManyRelatedManager
                        try:
                            return [str(item) for item in obj.all()]
                        except Exception:
                            return []
                    elif isinstance(obj, (list, tuple)):
                        return [convert_django_objects(item) for item in obj]
                    elif isinstance(obj, dict):
                        return {key: convert_django_objects(value) for key, value in obj.items()}
                    else:
                        try:
                            # Try to iterate and convert each item
                            return [convert_django_objects(item) for item in obj]
                        except (TypeError, AttributeError):
                            return str(obj)
                else:
                    # Handle individual Django model instances
                    if hasattr(obj, '_meta') and hasattr(obj, 'pk'):
                        # This is a Django model instance
                        return str(obj)
                    else:
                        return obj
            
            # Convert the user context
            safe_context = convert_django_objects(user_context)
            return json.dumps(safe_context, indent=2)
            
        except Exception as e:
            logger.warning(f"Failed to serialize user context safely: {str(e)}")
            # Fallback: create a simplified version
            safe_context = {}
            for key, value in user_context.items():
                try:
                    json.dumps(value)  # Test if it's already serializable
                    safe_context[key] = value
                except (TypeError, ValueError):
                    safe_context[key] = str(value)
            
            return json.dumps(safe_context, indent=2)
    
    def _clean_schema_for_openai(self, schema: dict) -> dict:
        """Clean Pydantic schema for OpenAI compatibility"""
        import copy
        
        def clean_recursively(obj):
            if isinstance(obj, dict):
                cleaned = {}
                for key, value in obj.items():
                    if key in ['allOf', 'anyOf', 'oneOf', 'default', 'format', 'examples', 'const']:
                        continue
                    elif key == 'enum' and isinstance(value, list):
                        cleaned[key] = value
                    elif key == 'type' and value == 'null':
                        continue
                    else:
                        cleaned[key] = clean_recursively(value)
                
                if cleaned.get('type') == 'object' and 'additionalProperties' not in cleaned:
                    cleaned['additionalProperties'] = False
                
                return cleaned
            elif isinstance(obj, list):
                return [clean_recursively(item) for item in obj]
            else:
                return obj
        
        return clean_recursively(schema)

# Utility functions for integration

def analyze_email_intent(email_content: str, openai_client: OpenAI, user_context: Optional[Dict] = None) -> IntentAnalysisResult:
    """
    Convenience function to analyze email intent
    
    Args:
        email_content: Email content to analyze
        openai_client: OpenAI client instance
        user_context: Optional user context
        
    Returns:
        IntentAnalysisResult
    """
    analyzer = EmailIntentAnalyzer(openai_client)
    return analyzer.analyze_intent(email_content, user_context)

def get_predicted_tools_for_intent(intent: str) -> List[str]:
    """
    Get predicted tools for a given intent category
    
    Args:
        intent: Intent category name
        
    Returns:
        List of tool names
    """
    return EmailIntentAnalyzer.INTENT_TOOL_MAPPINGS.get(intent, [])

# Example usage and testing
if __name__ == "__main__":
    # Example usage
    from openai import OpenAI
    import os
    
    client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
    analyzer = EmailIntentAnalyzer(client)
    
    # Test cases
    test_emails = [
        "Hi, can you create a meal plan for this week? I'm vegetarian and allergic to nuts.",
        "I need a shopping list for my meal plan. Can you send me an Instacart link?",
        "How do I cook the chicken parmesan from my meal plan? I need step by step instructions.",
        "Are there any local chefs in my area? I'd like to order some fresh meals.",
        "I need to pay for my order #12345. Can you send me the payment link?"
    ]
    
    for i, email in enumerate(test_emails):
        print(f"\n--- Test Email {i+1} ---")
        print(f"Content: {email}")
        
        result = analyzer.analyze_intent(email)
        print(f"Intent: {result.intent.primary_intent}")
        print(f"Confidence: {result.intent.confidence}")
        print(f"Predicted Tools: {result.intent.predicted_tools}")
        print(f"Processing Time: {result.processing_time:.2f}s")
