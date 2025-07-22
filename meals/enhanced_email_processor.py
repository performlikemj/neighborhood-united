"""
Enhanced Email Processor with Intent Analysis and Tool-Specific Formatting

This module integrates the intent analysis and tool-specific formatting systems
with the existing Django email processing workflow.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import time
from django.http import JsonResponse
# Import our new components
from meals.intent_analyzer import EmailIntentAnalyzer, IntentAnalysisResult, EmailIntent
from customer_dashboard.tool_specific_formatters_instacart_compliant import (
    ToolSpecificFormatterManager, FormattedContent
)
import traceback
import re

logger = logging.getLogger(__name__)

@dataclass
class DjangoEmailBody:
    """Container for Django template email body sections"""
    email_body_main: str
    email_body_data: str
    email_body_final: str
    css_classes: List[str]
    metadata: Dict[str, Any]

class EnhancedEmailProcessor:
    """
    Enhanced email processor that uses intent analysis and tool-specific formatting
    """
    
    def __init__(self, openai_client, meal_planning_assistant):
        self.openai_client = openai_client
        self.assistant = meal_planning_assistant
        self.intent_analyzer = EmailIntentAnalyzer(openai_client)
    
    def process_and_reply_to_email(
        self, 
        email_content: str, 
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Enhanced email processing with intent analysis and tool-specific formatting
        
        Args:
            email_content: The raw email content
            user_context: Optional user context information
            
        Returns:
            Dictionary containing the formatted response and metadata
        """
        start_time = time.time()
        
        try:
            # Step 1: Analyze intent
            logger.info("Starting intent analysis...")
            intent_result = self.intent_analyzer.analyze_intent(email_content, user_context)
            
            # Step 1.5: Clean email headers from content
            cleaned_email_content = self._remove_email_headers(email_content)
            logger.info(f"Email headers removal: original length={len(email_content)}, cleaned length={len(cleaned_email_content)}")
            
            # Step 2: Process with assistant (with intent awareness)
            logger.info(f"Processing with assistant (predicted tools: {intent_result.intent.predicted_tools})")
            assistant_response = self._process_with_assistant_awareness(
                cleaned_email_content, 
                intent_result.intent,
                user_context
            )
            
            # Step 3: Apply tool-specific formatting
            logger.info("Applying tool-specific formatting...")
            formatted_body = self._apply_tool_specific_formatting(
                assistant_response,
                intent_result.intent,
                user_context
            )
            
            # Step 4: Prepare final response
            processing_time = time.time() - start_time
            
            response = {
                'status': 'success',
                'email_body_main': formatted_body.email_body_main,
                'email_body_data': formatted_body.email_body_data,
                'email_body_final': formatted_body.email_body_final,
                'css_classes': formatted_body.css_classes,
                'metadata': {
                    **formatted_body.metadata,
                    'intent_analysis': intent_result.intent.model_dump(),
                    'processing_time': processing_time,
                    'tools_used': self._extract_tools_used(assistant_response),
                    'formatting_applied': True
                }
            }
            
            logger.info(f"Enhanced email processing completed in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Error in enhanced email processing: {str(e)}")
            # Fallback to original processing
            return self._fallback_processing(email_content, user_context)
    
    def _process_with_assistant_awareness(
        self, 
        email_content: str, 
        intent: EmailIntent,
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process email with the assistant, using intent information to guide processing
        """
        # Add intent context to the assistant processing
        enhanced_context = {
            **(user_context or {}),
            'predicted_intent': intent.primary_intent,
            'predicted_tools': intent.predicted_tools,
            'content_complexity': intent.content_structure,
            'requires_action': intent.user_action_required
        }
        
        # Use the existing assistant processing but with enhanced context
        # This assumes the MealPlanningAssistant has a method to process messages
        try:
            # Call the assistant's message processing method
            response = self.assistant.send_message(email_content)
            
            # Enhance the response with intent information
            if isinstance(response, dict):
                response['intent_context'] = enhanced_context
            
            return response
            
        except Exception as e:
            logger.error(f"Error in assistant processing: {str(e)}")
            # Return a basic response structure
            return {
                'status': 'error',
                'message': str(e),
                'tool_calls': [],
                'intent_context': enhanced_context
            }
    
    def _apply_tool_specific_formatting(
        self,
        assistant_response: Dict[str, Any],
        intent: EmailIntent,
        user_context: Optional[Dict] = None
    ) -> DjangoEmailBody:
        """
        Apply tool-specific formatting to the assistant response
        """
        try:
            # 🔍 DIAGNOSTIC: Log formatting attempt
            logger.info(f"=== TOOL-SPECIFIC FORMATTING START ===")
            logger.info(f"Intent: {intent.primary_intent}")
            logger.info(f"Predicted tools: {intent.predicted_tools}")
            
            # Extract message content from assistant response
            message_content = ""
            if isinstance(assistant_response, dict):
                message_content = assistant_response.get('message', str(assistant_response))
            else:
                message_content = str(assistant_response)
            
            logger.info(f"Message content preview: {repr(message_content[:200])}")
            
            # Check if content contains Instacart links
            if 'instacart' in message_content.lower():
                logger.info("✅ Instacart content detected, applying Instacart formatter")
                
                # Use the ToolSpecificFormatterManager to format content
                formatter_manager = ToolSpecificFormatterManager()
                
                # Determine appropriate tools for content
                detected_tools = self._detect_tools_from_content(message_content, intent)
                logger.info(f"Detected tools from content: {detected_tools}")
                
                # Format the content
                formatted_content = formatter_manager.format_content(
                    message_content, 
                    detected_tools, 
                    user_context
                )
                
                logger.info(f"Formatter returned: main_content length={len(formatted_content.main_content)}, data_content length={len(formatted_content.data_content)}")
                
                # Convert to DjangoEmailBody
                return DjangoEmailBody(
                    email_body_main=formatted_content.main_content,
                    email_body_data=formatted_content.data_content,
                    email_body_final=formatted_content.final_content,
                    css_classes=['enhanced-formatting', 'instacart-formatted'],
                    metadata={
                        'formatting_type': 'tool_specific',
                        'intent_category': intent.primary_intent,
                        'detected_tools': detected_tools,
                        'formatting_timestamp': datetime.now().isoformat()
                    }
                )
            else:
                logger.info("❌ No Instacart content detected")
            
            # Extract tool outputs from assistant response (for other tools)
            tool_outputs = self._extract_tool_outputs(assistant_response)
            
            if not tool_outputs:
                logger.info("No tool outputs found, applying general formatting")
                # No tools used, apply general formatting
                return self._apply_general_formatting(assistant_response, intent)
            
            logger.info(f"Found {len(tool_outputs)} tool outputs")
            
            # For non-Instacart tools, we'd format them here
            # For now, fall back to general formatting
            return self._apply_general_formatting(assistant_response, intent)
            
        except Exception as e:
            logger.error(f"Error in tool-specific formatting: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback to general formatting
            return self._apply_general_formatting(assistant_response, intent)
        finally:
            logger.info(f"=== TOOL-SPECIFIC FORMATTING END ===")
    
    def _detect_tools_from_content(self, content: str, intent: EmailIntent) -> List[str]:
        """
        Detect which tools should be used based on content analysis
        """
        detected_tools = []
        
        # Check for shopping list indicators
        if any(indicator in content.lower() for indicator in ['shopping list', 'grocery', '—', '•']):
            detected_tools.append('shopping_list_tool')
        
        # Check for recipe indicators
        if any(indicator in content.lower() for indicator in ['recipe', 'ingredient', 'cooking', 'preparation']):
            detected_tools.append('recipe_tool')
        
        # Check for meal plan indicators  
        if any(indicator in content.lower() for indicator in ['meal plan', 'weekly plan', 'monday', 'tuesday']):
            detected_tools.append('meal_plan_tool')
        
        # Fallback to intent predicted tools
        if not detected_tools:
            detected_tools = intent.predicted_tools or ['general']
        
        return detected_tools
    
    def _remove_email_headers(self, email_content: str) -> str:
        """
        Remove email headers (From:, Date:, Subject:, etc.) from email content
        """
        # Common email headers to remove
        header_patterns = [
            r'^From:.*$',
            r'^To:.*$', 
            r'^Date:.*$',
            r'^Subject:.*$',
            r'^Reply-To:.*$',
            r'^CC:.*$',
            r'^BCC:.*$',
            r'^Message-ID:.*$',
            r'^In-Reply-To:.*$',
            r'^References:.*$',
            r'^MIME-Version:.*$',
            r'^Content-Type:.*$',
            r'^Content-Transfer-Encoding:.*$',
            r'^X-.*:.*$',  # X-headers
        ]
        
        lines = email_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines at the beginning
            if not line_stripped and not cleaned_lines:
                continue
                
            # Check if line matches any header pattern
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_header = True
                    logger.info(f"Removing email header: {line_stripped[:50]}...")
                    break
            
            if not is_header:
                cleaned_lines.append(line)
        
        # Join lines and clean up extra whitespace
        cleaned_content = '\n'.join(cleaned_lines)
        cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_content)  # Remove excessive blank lines
        cleaned_content = cleaned_content.strip()
        
        return cleaned_content
    
    def _extract_tool_outputs(self, assistant_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool outputs from assistant response
        """
        tool_outputs = []
        
        # Handle different response structures
        if 'tool_calls' in assistant_response:
            for tool_call in assistant_response['tool_calls']:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('function', {}).get('name', 'unknown')
                    tool_output = tool_call.get('result', {})
                    
                    tool_outputs.append({
                        'tool_name': tool_name,
                        'output': tool_output,
                        'call_id': tool_call.get('id', ''),
                        'timestamp': tool_call.get('timestamp', datetime.now().isoformat())
                    })
        
        # Handle direct tool results in response
        elif 'tools_used' in assistant_response:
            for tool_name, tool_result in assistant_response['tools_used'].items():
                tool_outputs.append({
                    'tool_name': tool_name,
                    'output': tool_result,
                    'call_id': f"{tool_name}_{int(time.time())}",
                    'timestamp': datetime.now().isoformat()
                })
        
        return tool_outputs
    
    def _distribute_sections_to_template(
        self, 
        formatted_sections: List[FormattedContent], 
        intent: EmailIntent
    ) -> DjangoEmailBody:
        """
        Distribute formatted sections across Django template sections
        """
        # Initialize template sections
        main_sections = []
        data_sections = []
        final_sections = []
        all_css_classes = []
        
        # Distribute sections by type
        for section in formatted_sections:
            all_css_classes.extend(section.css_classes)
            
            if section.section_type == "main":
                main_sections.append(section.content)
            elif section.section_type == "data":
                data_sections.append(section.content)
            elif section.section_type == "final":
                final_sections.append(section.content)
        
        # Combine sections with appropriate spacing
        email_body_main = self._combine_sections(main_sections)
        email_body_data = self._combine_sections(data_sections)
        email_body_final = self._combine_sections(final_sections)
        
        # Add default content if sections are empty
        if not email_body_main:
            email_body_main = self._get_default_main_content(intent)
        
        # Create metadata
        metadata = {
            'sections_count': len(formatted_sections),
            'main_sections': len(main_sections),
            'data_sections': len(data_sections),
            'final_sections': len(final_sections),
            'intent_category': intent.primary_intent,
            'formatting_timestamp': datetime.now().isoformat()
        }
        
        return DjangoEmailBody(
            email_body_main=email_body_main,
            email_body_data=email_body_data,
            email_body_final=email_body_final,
            css_classes=list(set(all_css_classes)),  # Remove duplicates
            metadata=metadata
        )
    
    def _combine_sections(self, sections: List[str]) -> str:
        """
        Combine multiple sections with appropriate spacing
        """
        if not sections:
            return ""
        
        # Join sections with spacing
        combined = "\n\n".join(section.strip() for section in sections if section.strip())
        
        # Wrap in container div
        if combined:
            return f'<div class="email-section">{combined}</div>'
        
        return ""
    
    def _get_default_main_content(self, intent: EmailIntent) -> str:
        """
        Get default main content based on intent
        """
        intent_greetings = {
            "meal_planning": "🍽️ Here's your meal planning information:",
            "shopping": "🛒 Here's your shopping information:",
            "recipe_request": "👨‍🍳 Here are your recipe details:",
            "nutrition_info": "📊 Here's your nutritional information:",
            "chef_connection": "👨‍🍳 Here are your chef connection details:",
            "payment_order": "💳 Here's your order information:",
            "dietary_preferences": "🥗 Here's your dietary information:",
            "pantry_management": "🏠 Here's your pantry information:",
            "general_question": "ℹ️ Here's the information you requested:"
        }
        
        greeting = intent_greetings.get(intent.primary_intent, "ℹ️ Here's your information:")
        
        return f"""
        <div class="email-greeting">
            <h2>{greeting}</h2>
            <p>We've processed your request and prepared the information below.</p>
        </div>
        """
    
    def _apply_general_formatting(
        self, 
        assistant_response: Dict[str, Any], 
        intent: EmailIntent
    ) -> DjangoEmailBody:
        """
        Apply general formatting when no specific tools are used
        """
        # Extract message content
        message_content = ""
        if 'message' in assistant_response:
            message_content = assistant_response['message']
        elif 'response' in assistant_response:
            message_content = assistant_response['response']
        elif 'content' in assistant_response:
            message_content = assistant_response['content']
        
        # Apply basic HTML formatting
        formatted_content = self._format_text_content(message_content)
        
        # Create main section
        main_content = self._get_default_main_content(intent)
        
        # Put formatted content in data section
        data_content = f'<div class="general-response">{formatted_content}</div>' if formatted_content else ""
        
        # Create final section with general actions
        final_content = self._get_general_final_content(intent)
        
        metadata = {
            'formatting_type': 'general',
            'intent_category': intent.primary_intent,
            'has_content': bool(formatted_content),
            'formatting_timestamp': datetime.now().isoformat()
        }
        
        return DjangoEmailBody(
            email_body_main=main_content,
            email_body_data=data_content,
            email_body_final=final_content,
            css_classes=['general-formatting', f'intent-{intent.primary_intent}'],
            metadata=metadata
        )
    
    def _format_text_content(self, content: str) -> str:
        """
        Apply basic HTML formatting to text content
        """
        if not content or not isinstance(content, str):
            return ""
        
        # Convert line breaks to HTML
        formatted = content.replace('\n\n', '</p><p>').replace('\n', '<br>')
        
        # Wrap in paragraphs
        if formatted:
            formatted = f'<p>{formatted}</p>'
        
        # Basic markdown-style formatting
        formatted = formatted.replace('**', '<strong>').replace('**', '</strong>')
        formatted = formatted.replace('*', '<em>').replace('*', '</em>')
        
        return formatted
    
    def _get_general_final_content(self, intent: EmailIntent) -> str:
        """
        Get general final content based on intent
        """
        if intent.user_action_required:
            return """
            <div class="general-actions">
                <p>Need help with anything else? Just reply to this email!</p>
            </div>
            """
        
        return """
        <div class="general-footer">
            <p>Thanks for using our meal planning service! Reply if you need anything else.</p>
        </div>
        """
    
    def _extract_tools_used(self, assistant_response: Dict[str, Any]) -> List[str]:
        """
        Extract list of tools used from assistant response
        """
        tools_used = []
        
        if 'tool_calls' in assistant_response:
            for tool_call in assistant_response['tool_calls']:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('function', {}).get('name')
                    if tool_name:
                        tools_used.append(tool_name)
        
        elif 'tools_used' in assistant_response:
            tools_used = list(assistant_response['tools_used'].keys())
        
        return tools_used
    
    def _fallback_processing(
        self, 
        email_content: str, 
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Fallback to original processing when enhanced processing fails
        """
        logger.warning("Falling back to original email processing")
        
        try:
            # Use the original assistant processing
            response = self.assistant.send_message(email_content)
            
            # Apply basic formatting
            if isinstance(response, dict) and 'message' in response:
                formatted_content = self._format_text_content(response['message'])
                
                return {
                    'status': 'success',
                    'email_body_main': '<h2>ℹ️ Your Request</h2><p>Here\'s the information you requested:</p>',
                    'email_body_data': f'<div class="fallback-content">{formatted_content}</div>',
                    'email_body_final': '<p>Thanks for using our service!</p>',
                    'css_classes': ['fallback-formatting'],
                    'metadata': {
                        'formatting_type': 'fallback',
                        'enhanced_processing': False,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Fallback processing also failed: {str(e)}")
            return {
                'status': 'error',
                'message': f'Email processing failed: {str(e)}',
                'email_body_main': '<h2>❌ Processing Error</h2>',
                'email_body_data': '<p>We encountered an error processing your request. Please try again.</p>',
                'email_body_final': '<p>If the problem persists, please contact support.</p>',
                'css_classes': ['error-formatting'],
                'metadata': {
                    'formatting_type': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
            }

# Integration functions for Django views

def create_enhanced_email_processor(openai_client, meal_planning_assistant) -> EnhancedEmailProcessor:
    """
    Factory function to create an enhanced email processor
    """
    return EnhancedEmailProcessor(openai_client, meal_planning_assistant)

def process_email_with_enhanced_formatting(
    email_content: str,
    openai_client,
    meal_planning_assistant,
    user_context: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Convenience function to process an email with enhanced formatting
    
    Args:
        email_content: The email content to process
        openai_client: OpenAI client instance
        meal_planning_assistant: MealPlanningAssistant instance
        user_context: Optional user context
        
    Returns:
        Formatted email response
    """
    processor = create_enhanced_email_processor(openai_client, meal_planning_assistant)
    return processor.process_and_reply_to_email(email_content, user_context)

# Django view integration example

def enhanced_process_email_view(request):
    """
    Example Django view using the enhanced email processor
    
    This would replace or enhance the existing process_email view
    """
    try:
        # Parse request (same as original)
        data = json.loads(request.body)
        sender_email = data.get('sender_email')
        token = data.get('token')
        message_content = data.get('message_content')
        user_id = data.get('user_id')
        
        # Validate token and get user (same as original)
        # ... token validation code ...
        
        # Create enhanced processor
        from openai import OpenAI
        from meals.meal_assistant_implementation import MealPlanningAssistant
        
        openai_client = OpenAI()
        assistant = MealPlanningAssistant(user_id)
        
        # Process with enhanced formatting
        result = process_email_with_enhanced_formatting(
            message_content,
            openai_client,
            assistant,
            user_context={'user_id': user_id, 'sender_email': sender_email}
        )
        
        # Add token for n8n reply
        result['token'] = token
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in enhanced email processing view: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to process email: {str(e)}'
        }, status=500)

# Example usage and testing
if __name__ == "__main__":
    # Test the enhanced processor
    from openai import OpenAI
    import os
    
    # Mock assistant for testing
    class MockAssistant:
        def send_message(self, message):
            return {
                'status': 'success',
                'message': 'Here is your meal plan for this week...',
                'tool_calls': [
                    {
                        'id': 'call_123',
                        'function': {'name': 'create_meal_plan'},
                        'result': {
                            'meal_plan': {
                                'id': 123,
                                'week_start_date': '2024-01-15',
                                'meals': [
                                    {'day': 'Monday', 'meal_type': 'Breakfast', 'meal_name': 'Oatmeal'}
                                ]
                            }
                        }
                    }
                ]
            }
    
    # Test processing
    client = OpenAI()
    assistant = MockAssistant()
    processor = EnhancedEmailProcessor(client, assistant)
    
    test_email = "Hi, can you create a meal plan for this week? I'm vegetarian."
    
    try:
        result = processor.process_and_reply_to_email(test_email)
        print("=== Enhanced Email Processing Test ===")
        print(f"Status: {result['status']}")
        print(f"Main section length: {len(result.get('email_body_main', ''))}")
        print(f"Data section length: {len(result.get('email_body_data', ''))}")
        print(f"Final section length: {len(result.get('email_body_final', ''))}")
        print(f"CSS classes: {result.get('css_classes', [])}")
        print(f"Intent: {result.get('metadata', {}).get('intent_analysis', {}).get('primary_intent', 'unknown')}")
    except Exception as e:
        print(f"Test failed: {e}")

