# meals/meal_assistant_implementation.py
import json, logging, uuid, traceback, sys
import time
from typing import Dict, Any, List, Generator, Optional, Union, ClassVar, Literal, Tuple
import numbers
from datetime import date, datetime
import re
from bs4 import BeautifulSoup   
from django.conf import settings
from django.conf.locale import LANG_INFO  # Add this import
from utils.redis_client import get, set, delete
from django.utils import timezone
from openai import OpenAI
from openai.types.responses import (
    # high‑level lifecycle events
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseCompletedEvent,
    # assistant message streaming
    ResponseOutputMessage,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseContentPartAddedEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    # function‑calling events
    ResponseFunctionToolCall,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
)
from openai import BadRequestError
from django_countries.fields import Country
import decimal as _decimal
import datetime as _dt
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from .tool_registration import get_all_tools, get_all_guest_tools, handle_tool_call
from customer_dashboard.models import ChatThread, UserMessage, WeeklyAnnouncement, UserDailySummary, UserChatSummary, AssistantEmailToken
from custom_auth.models import CustomUser
from shared.utils import generate_user_context, _get_language_name
from utils.model_selection import choose_model
import pytz
from zoneinfo import ZoneInfo
from local_chefs.models import ChefPostalCode
from django.db.models import F
from meals.models import ChefMealEvent
from dotenv import load_dotenv
import os
import requests # Added for n8n webhook call
import traceback
from django.template.loader import render_to_string # Added for rendering email templates
from django.db import close_old_connections, connection
from django.db.utils import OperationalError, InterfaceError, DatabaseError

# Add the translation utility
from utils.translate_html import translate_paragraphs
import unicodedata
from enum import Enum


load_dotenv()

# Control character regex for JSON sanitization
CTRL_CHARS = re.compile(r'[\x00-\x1F]')

def _json_default(obj):
    try:
        if isinstance(obj, Country):
            try:
                return obj.code or str(obj)
            except Exception:
                return str(obj)
    except Exception:
        pass
    try:
        if isinstance(obj, _decimal.Decimal):
            return float(obj)
    except Exception:
        pass
    try:
        if isinstance(obj, (_dt.date, _dt.datetime)):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)

def _safe_json_dumps(obj) -> str:
    return json.dumps(obj, default=_json_default)

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

class PasswordPrompt(BaseModel):
    """Structured output emitted by the model whenever it wants the user to enter
    their account password."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    assistant_message: str = Field(
        ...,
        description="The natural-language text that will be displayed verbatim in the UI."
    )
    is_password_request: bool = Field(
        ...,
        description="Must be true when the assistant requests the user's password."
    )

    example: ClassVar[Dict[str, Any]] = {
        "assistant_message": "For security we need your account password.",
        "is_password_request": True
    }

class EmailBody(BaseModel):
    """
    Structured HTML content for email generation.

    * main_section – primary response content (HTML allowed)
    * data_visualization – OPTIONAL additional HTML (tables/charts) for structured data
    * final_message – closing paragraph guiding the user on next steps or summarising key points
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    main_section: str = Field(..., description="Primary response content in HTML")
    data_visualization: Optional[str] = Field(
        ..., description="Optional HTML block for charts/tables/lists"
    )
    final_message: str = Field(..., description="Closing message in HTML. This should be a short message that guides the user on next steps or summarises key points without being too verbose.")

class ChatRender(BaseModel):
    """Structured chat rendering payload for frontend consumption.
    Ensures the assistant output is valid GitHub‑Flavored Markdown (GFM).
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    markdown: str = Field(..., description="Final GFM content suitable for ReactMarkdown/remark-gfm")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata such as date_range or layout hints")

# EmailResponse model removed - EmailBody now handles all email formatting

# ────────────────────────────────────────────────────────────────────
#  Django Template-Compatible Enhanced Email Formatter
# ────────────────────────────────────────────────────────────────────

# Define content and format types as string literals to avoid OpenAI JSON schema issues
CONTENT_TYPES = [
    "recipe", "shopping_list", "meal_plan", "nutrition_info", 
    "instructions", "general_text", "data_table", "comparison"
]

FORMAT_TYPES = [
    "paragraph", "unordered_list", "ordered_list", 
    "table", "definition_list", "heading"
]

class ContentSection(BaseModel):
    """Individual content section with intelligent formatting"""
    model_config = ConfigDict(extra="forbid")
    
    title: Optional[str] = Field(None, description="Section title if applicable")
    content_type: Literal["recipe", "shopping_list", "meal_plan", "nutrition_info", "instructions", "general_text", "data_table", "comparison"] = Field(..., description="Type of content for intelligent formatting")
    format_type: Literal["paragraph", "unordered_list", "ordered_list", "table", "definition_list", "heading"] = Field(..., description="HTML format to use")
    content: str = Field(..., description="HTML formatted content")
    priority: int = Field(1, description="Display priority (1=highest, 5=lowest)")
    template_section: Literal["main", "data", "final"] = Field("main", description="Which Django template section this belongs to")

class ContentAnalysis(BaseModel):
    """Analysis of the input content for intelligent formatting decisions"""
    model_config = ConfigDict(extra="forbid")
    
    primary_content_type: Literal["recipe", "shopping_list", "meal_plan", "nutrition_info", "instructions", "general_text", "data_table", "comparison"] = Field(..., description="Main type of content detected")
    has_structured_data: bool = Field(..., description="Whether content contains tables/lists")
    has_actionable_items: bool = Field(..., description="Whether content has action items/CTAs")
    complexity_level: Literal["simple", "moderate", "complex"] = Field(..., description="Content complexity")
    recommended_organization: str = Field(..., description="Recommended content organization approach")

class DjangoEmailBody(BaseModel):
    """Django template-compatible email body structure"""
    model_config = ConfigDict(extra="forbid")
    
    # Content analysis for intelligent formatting decisions
    content_analysis: ContentAnalysis = Field(..., description="Analysis of content structure and type")
    
    # Organized content sections in priority order
    sections: List[ContentSection] = Field(..., description="Content sections in display order")
    
    # Django template sections
    email_body_main: str = Field(..., description="Main content for {{ email_body_main|safe }}")
    email_body_data: str = Field(..., description="Data visualization for {{ email_body_data|safe }}")
    email_body_final: str = Field(..., description="Final message for {{ email_body_final|safe }}")
    
    # Metadata for rendering
    email_subject_suggestion: Optional[str] = Field(None, description="Suggested email subject line")
    estimated_read_time: Optional[str] = Field(None, description="Estimated reading time")

class DjangoTemplateEmailFormatter:
    """Django template-compatible enhanced email formatter"""
    
    def __init__(self, openai_client):
        self.client = openai_client
        
    def format_text_for_email_body(self, raw_text: str) -> str:
        """
        Transform plain text into Django template-compatible HTML sections.
        Returns the main content section for backward compatibility.
        Use get_django_template_sections() for full template integration.
        
        Args:
            raw_text: The raw text content to format
            
        Returns:
            Formatted HTML string for email_body_main (backward compatible)
        """
        django_body = self.get_django_template_sections(raw_text)
        return django_body.email_body_main
    
    def get_django_template_sections(self, raw_text: str, intent_context: Optional[Dict] = None) -> DjangoEmailBody:
        """
        Get all Django template sections for complete integration.
        
        Args:
            raw_text: The raw text content to format
            intent_context: Optional intent analysis context for better formatting
            
        Returns:
            DjangoEmailBody with email_body_main, email_body_data, and email_body_final
        """
        
        # Guard rails
        if not raw_text.strip():
            return DjangoEmailBody(
                content_analysis=ContentAnalysis(
                    primary_content_type="general_text",
                    has_structured_data=False,
                    has_actionable_items=False,
                    complexity_level="simple",
                    recommended_organization="Empty content"
                ),
                sections=[],
                email_body_main="",
                email_body_data="",
                email_body_final=""
            )
            
        if not self.client:
            # Offline fallback
            safe_fallback = raw_text.replace("\n", "<br>")
            fallback_html = f"<p>{safe_fallback}</p>"
            return DjangoEmailBody(
                content_analysis=ContentAnalysis(
                    primary_content_type="general_text",
                    has_structured_data=False,
                    has_actionable_items=False,
                    complexity_level="simple",
                    recommended_organization="Fallback formatting"
                ),
                sections=[],
                email_body_main=fallback_html,
                email_body_data="",
                email_body_final=""
            )
        
        try:
            # Clean up input text
            cleaned_text = self._clean_input_text(raw_text)
            
            # Protect URLs with placeholders
            protected_text, url_placeholders = self._protect_urls(cleaned_text)
            
            # Get structured formatting from OpenAI
            django_body = self._get_structured_django_formatting(protected_text, intent_context)
            
            # Render sections to HTML
            self._render_django_sections(django_body)
            
            # Restore URLs in all sections
            django_body.email_body_main = self._restore_urls(django_body.email_body_main, url_placeholders)
            django_body.email_body_data = self._restore_urls(django_body.email_body_data, url_placeholders)
            django_body.email_body_final = self._restore_urls(django_body.email_body_final, url_placeholders)
            
            # Apply final formatting to all sections
            django_body.email_body_main = self._apply_final_formatting(django_body.email_body_main)
            django_body.email_body_data = self._apply_final_formatting(django_body.email_body_data)
            django_body.email_body_final = self._apply_final_formatting(django_body.email_body_final)
            
            # 🔍 DIAGNOSTIC: Log what OpenAI produced for each section analysis
            logger.info(f"=== DJANGO TEMPLATE SECTIONS ANALYSIS ===")
            logger.info(f"Content Analysis: {django_body.content_analysis.primary_content_type} (complexity: {django_body.content_analysis.complexity_level})")
            logger.info(f"Sections Count: {len(django_body.sections)}")
            
            for i, section in enumerate(django_body.sections):
                logger.info(f"Section {i}: {section.content_type} -> {section.template_section} (priority: {section.priority})")
                logger.info(f"  Title: {section.title}")
                logger.info(f"  Format: {section.format_type}")
                logger.info(f"  Content preview: {repr(section.content[:200])}")
            
            return django_body
            
        except Exception as e:
            logger.error(f"Error in get_django_template_sections: {str(e)}")
            self._send_error_to_n8n(e, "get_django_template_sections")
            
            # Fallback formatting
            return self._create_fallback_django_body(raw_text)
    
    def _clean_input_text(self, text: str) -> str:
        """Clean and normalize input text"""
        
        try:
            # Ensure proper UTF-8 encoding
            text = text.encode('utf-8', errors='replace').decode('utf-8')
            # Normalize Unicode characters
            text = unicodedata.normalize('NFC', text)
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            text = unicodedata.normalize('NFC', text)
            logger.warning(f"Unicode encoding issue: {e}")
        
        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _protect_urls(self, text: str) -> tuple[str, dict]:
        """Protect URLs with placeholders to prevent corruption"""
        url_pattern = r'https?://[^\s<>"\'()]+[^\s<>"\'.!?;,)]'
        urls = re.findall(url_pattern, text)
        url_placeholders = {}
        
        protected_text = text
        for i, url in enumerate(urls):
            placeholder = f"__URL_PLACEHOLDER_{i}__"
            url_placeholders[placeholder] = url
            protected_text = protected_text.replace(url, placeholder)
        
        return protected_text, url_placeholders
    
    def _restore_urls(self, html: str, url_placeholders: dict) -> str:
        """Restore original URLs from placeholders"""
        for placeholder, original_url in url_placeholders.items():
            html = html.replace(placeholder, original_url)
        return html

    def _shape_chat_markdown(self, raw_text: str) -> Dict[str, Any]:
        """
        Ask the model to normalize the assistant's reply into strict GFM Markdown
        using a small structured JSON schema. Falls back to raw text on error.
        """
        try:
            schema = self._clean_schema_for_openai(ChatRender.model_json_schema())
            prompt = (
                "Return ONLY JSON with a `markdown` field that contains valid GitHub‑Flavored Markdown (GFM). "
                "Rules: Use headings, lists, and pipe tables when appropriate. "
                "For weekly meal plans, include a pipe table with columns | Day | Breakfast | Lunch | Dinner | and a separator row. "
                "Format date ranges like `Mon–Sun, Sep 8–14, 2025` using an en dash. "
                "Ensure a blank line before the table, preserve Unicode (NFC), and never include commentary outside JSON."
            )
            resp = self.client.responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "developer", "content": prompt},
                    {"role": "user", "content": f"RAW:\n{raw_text}"},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "chat_render",
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
            shaped = _safe_load_and_validate(ChatRender, resp.output_text)
            return shaped.model_dump()
        except Exception:
            # Fallback to raw text as GFM
            try:
                logger.warning("CHAT_RENDER shaping failed; falling back to raw text")
            except Exception:
                pass
            return {"markdown": raw_text}
    
    def _get_structured_django_formatting(self, text: str, intent_context: Optional[Dict] = None) -> DjangoEmailBody:
        """Get structured formatting from OpenAI responses API for Django template"""
        
        # Build intent-aware prompt
        intent_guidance = ""
        if intent_context:
            primary_intent = intent_context.get('primary_intent', 'general')
            predicted_tools = intent_context.get('predicted_tools', [])
            content_structure = intent_context.get('content_structure', 'simple')
            
            intent_guidance = f"""
            
        INTENT CONTEXT:
        - Primary Intent: {primary_intent}
        - Predicted Tools: {', '.join(predicted_tools)}
        - Content Structure: {content_structure}
        
        INTENT-SPECIFIC FORMATTING RULES:
        - If intent is 'meal_planning': Focus main section on meal plans, data section on shopping lists/nutrition
        - If intent is 'recipe': Main section for recipes, data section for ingredients/instructions
        - If intent is 'shopping': Main section for overview, data section for structured shopping lists
        - If intent is 'dietary': Main section for dietary guidance, data section for comparison tables
        - Always use final section for next steps and call-to-action
        """
        
        prompt_content = f"""
        You are an expert email content formatter that creates beautifully structured HTML emails for Django templates.

        TASK: Analyze the input text and return a structured JSON response following the DjangoEmailBody schema.

        DJANGO TEMPLATE INTEGRATION:
        The output will be used in a Django template with three sections:
        - email_body_main: Primary content (recipes, instructions, main text)
        - email_body_data: Data visualization (tables, charts, structured data)
        - email_body_final: Closing message (call-to-action, next steps, summary)

        SECTION ASSIGNMENT RULES:
        - Main section: Core content, recipes, instructions, primary information
        - Data section: Tables, nutrition info, structured lists, comparisons
        - Final section: Call-to-action, next steps, closing thoughts, summaries

        CONTENT ANALYSIS REQUIREMENTS:
        1. Identify primary content type: recipe, shopping_list, meal_plan, nutrition_info, instructions, general_text, data_table, comparison
        2. Detect structured data (tables, lists, hierarchical content)
        3. Identify actionable items or calls-to-action
        4. Assess complexity: simple, moderate, complex

        SECTION ORGANIZATION:
        - Assign template_section: "main", "data", or "final" for each content section
        - Priority 1-2: Usually "main" section
        - Priority 3: Usually "data" section (tables, structured info)
        - Priority 4-5: Usually "final" section (CTAs, summaries)

        HTML CONTENT REQUIREMENTS:
        - Use semantic HTML optimized for the existing Django template CSS
        - The template has styles for: h1, h2, h3, p, ul, li, tables
        - Font family: Arial, sans-serif (already in template)
        - Preserve all numbers, measurements, and Unicode characters exactly
        - Preserve all __URL_PLACEHOLDER_X__ tokens exactly
        - Use existing CSS classes: .table-slim for tables

        {intent_guidance}

        RESPONSE FORMAT:
        Return ONLY a valid JSON object matching the DjangoEmailBody schema. No additional text.

        INPUT TEXT:
        {text}
        """
        
        try:
            # Clean the schema to remove OpenAI incompatible constructs
            schema = self._clean_schema_for_openai(DjangoEmailBody.model_json_schema())
            
            response = self.client.responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "developer", "content": "You are a precise Django template email formatter. Return ONLY structured JSON without commentary. Preserve all text exactly including measurements and placeholders."},
                    {"role": "user", "content": prompt_content}
                ],
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'django_email_body',
                        'schema': schema,
                        'strict': True
                    }
                }
            )
            
            # Parse and validate the response
            try:
                django_body = _safe_load_and_validate(DjangoEmailBody, response.output_text)
            except Exception as validation_error:
                logger.error(f"Pydantic validation failed even after JSON cleaning: {str(validation_error)}")
                logger.error(f"Cleaned JSON that failed: {repr(response.output_text[:500])}")
                # Force fallback to create_fallback_django_body
                raise Exception(f"JSON validation failed: {str(validation_error)}")
            
            # 🔍 DIAGNOSTIC: Log what OpenAI produced for each section analysis
            logger.info(f"=== DJANGO TEMPLATE SECTIONS ANALYSIS ===")
            logger.info(f"Content Analysis: {django_body.content_analysis.primary_content_type} (complexity: {django_body.content_analysis.complexity_level})")
            logger.info(f"Sections Count: {len(django_body.sections)}")
            
            for i, section in enumerate(django_body.sections):
                logger.info(f"Section {i}: {section.content_type} -> {section.template_section} (priority: {section.priority})")
                logger.info(f"  Title: {section.title}")
                logger.info(f"  Format: {section.format_type}")
                logger.info(f"  Content preview: {repr(section.content[:200])}")
            
            return django_body
            
        except Exception as e:
            logger.error(f"Error getting structured Django formatting: {str(e)}")
            self._send_error_to_n8n(e, "_get_structured_django_formatting")
            
            # Create fallback structured response
            return self._create_fallback_django_body(text)
    
    def _clean_schema_for_openai(self, schema: dict) -> dict:
        """
        Clean Pydantic v2 generated schema to be compatible with OpenAI's structured output API.
        Removes unsupported constructs like allOf, anyOf, default values, format fields, etc.
        """
        import copy
        
        def clean_recursively(obj):
            if isinstance(obj, dict):
                # Create a new dict to avoid modifying the original
                cleaned = {}
                
                for key, value in obj.items():
                    # Skip unsupported schema properties
                    if key in ['allOf', 'anyOf', 'oneOf', 'default', 'format', 'examples', 'const']:
                        continue
                    
                    # Handle Literal fields that might create allOf constructs
                    if key == 'enum' and isinstance(value, list):
                        cleaned[key] = value
                    elif key == 'type' and value == 'null':
                        # Skip null types as they're usually part of Optional which creates allOf
                        continue
                    else:
                        cleaned[key] = clean_recursively(value)
                
                # Ensure additionalProperties is explicitly set to False for objects
                if cleaned.get('type') == 'object' and 'additionalProperties' not in cleaned:
                    cleaned['additionalProperties'] = False
                
                # CRITICAL: Ensure all properties are in the required array for OpenAI
                if cleaned.get('type') == 'object' and 'properties' in cleaned:
                    all_property_keys = list(cleaned['properties'].keys())
                    cleaned['required'] = all_property_keys
                    
                    # Handle optional fields by making their types unions with null
                    for prop_name, prop_schema in cleaned['properties'].items():
                        if isinstance(prop_schema, dict):
                            # Check if this was an optional field (originally had anyOf with null)
                            if prop_name in ['title', 'email_subject_suggestion', 'estimated_read_time']:
                                # Make these fields nullable
                                if 'type' in prop_schema and prop_schema['type'] != 'null':
                                    prop_schema['type'] = [prop_schema['type'], 'null']
                
                # Handle Literal types and nested model references
                if 'allOf' in obj or 'anyOf' in obj:
                    # Try to extract a simple enum if possible
                    enum_values = []
                    ref_found = None
                    
                    if 'allOf' in obj:
                        for item in obj['allOf']:
                            if isinstance(item, dict):
                                if 'const' in item:
                                    enum_values.append(item['const'])
                                elif '$ref' in item:
                                    ref_found = item['$ref']
                    if 'anyOf' in obj:
                        for item in obj['anyOf']:
                            if isinstance(item, dict):
                                if 'const' in item:
                                    enum_values.append(item['const'])
                                elif '$ref' in item:
                                    ref_found = item['$ref']
                    
                    if enum_values:
                        return {
                            'type': 'string',
                            'enum': enum_values
                        }
                    elif ref_found:
                        # For nested model references, return the $ref directly
                        return {'$ref': ref_found}
                    else:
                        # Fallback to string type for complex Literal fields
                        return {'type': 'string'}
                
                return cleaned
                
            elif isinstance(obj, list):
                return [clean_recursively(item) for item in obj]
            else:
                return obj
        
        return clean_recursively(schema)
    
    def _render_django_sections(self, django_body: DjangoEmailBody) -> None:
        """Render the structured content to Django template sections"""
        
        # Initialize sections
        main_parts = []
        data_parts = []
        final_parts = []
        
        # Sort sections by priority
        sorted_sections = sorted(django_body.sections, key=lambda x: (x.priority, x.content_type))
        
        # Render each section to appropriate template section
        for section in sorted_sections:
            section_html = self._render_section(section)
            if section_html:
                if section.template_section == "main":
                    main_parts.append(section_html)
                elif section.template_section == "data":
                    data_parts.append(section_html)
                elif section.template_section == "final":
                    final_parts.append(section_html)
        
        # Combine sections
        django_body.email_body_main = '\n'.join(main_parts)
        django_body.email_body_data = '\n'.join(data_parts)
        django_body.email_body_final = '\n'.join(final_parts)
        
        # 🔍 DIAGNOSTIC: Log final rendered sections
        logger.info(f"=== FINAL DJANGO TEMPLATE SECTIONS ===")
        logger.info(f"EMAIL_BODY_MAIN length: {len(django_body.email_body_main)}")
        logger.info(f"EMAIL_BODY_MAIN preview: {repr(django_body.email_body_main[:300])}")
        logger.info(f"EMAIL_BODY_DATA length: {len(django_body.email_body_data)}")
        logger.info(f"EMAIL_BODY_DATA preview: {repr(django_body.email_body_data[:300])}")
        logger.info(f"EMAIL_BODY_FINAL length: {len(django_body.email_body_final)}")
        logger.info(f"EMAIL_BODY_FINAL preview: {repr(django_body.email_body_final[:300])}")
    
    def _render_section(self, section: ContentSection) -> str:
        """Render an individual content section with Django template-compatible styling"""
        html_parts = []
        
        # Add section title if present
        if section.title:
            html_parts.append(f'<h3>{section.title}</h3>')
        
        # Render content based on format type with Django template CSS compatibility
        if section.format_type == "paragraph":
            html_parts.append(f'<p>{section.content}</p>')
        
        elif section.format_type == "unordered_list":
            html_parts.append(f'<ul>{section.content}</ul>')
        
        elif section.format_type == "ordered_list":
            html_parts.append(f'<ol>{section.content}</ol>')
        
        elif section.format_type == "table":
            # Use Django template's table-slim class
            html_parts.append(f'<table class="table-slim">{section.content}</table>')
        
        elif section.format_type == "definition_list":
            html_parts.append(f'<dl>{section.content}</dl>')
        
        elif section.format_type == "heading":
            html_parts.append(f'<h3>{section.content}</h3>')
        
        else:
            # Default to paragraph
            html_parts.append(f'<p>{section.content}</p>')
        
        return '\n'.join(html_parts)

    def _format_instacart_button(self, url: str, text: str) -> str:
        """
        Return the Instacart call‑to‑action HTML that meets the latest
        partner‑branding specifications.

        • Height: 46px (div container)
        • Dynamic width: grows with text
        • Padding: 16px vertical × 18px horizontal
        • Logo: 22px tall
        • Border: #E8E9EB solid 0.5px
        • Background: #FFFFFF
        • Text color: #000000, 16px, semi-bold
        
        Button text options:
        • "Get Recipe Ingredients" (for recipe context)
        • "Get Ingredients" (when recipes are not included)
        • "Shop with Instacart" (legal approved)
        • "Order with Instacart" (legal approved)
        """
        # Validate button text is one of the approved options
        approved_texts = [
            "Get Recipe Ingredients", 
            "Get Ingredients", 
            "Shop with Instacart", 
            "Order with Instacart"
        ]
        
        if text not in approved_texts:
            # Default to "Shop with Instacart" if not an approved text
            text = "Shop with Instacart"
        
        # Append UTM parameters for affiliate tracking
        url_with_utm = _append_instacart_utm_params(url)
        
        return (
            f'<a href="{url_with_utm}" target="_blank" style="text-decoration:none;">'
            f'<div style="height:46px;display:inline-flex;align-items:center;'
            f'padding:16px 18px;background:#FFFFFF;border:0.5px solid #E8E9EB;'
            f'border-radius:8px;">'
            f'<img src="https://live.staticflickr.com/65535/54538897116_fb233f397f_m.jpg" '
            f'alt="Instacart" style="height:22px;width:auto;margin-right:10px;">'
            f'<span style="font-family:Arial,sans-serif;font-size:16px;'
            f'font-weight:500;color:#000000;white-space:nowrap;">{text}</span>'
            f'</div></a>'
        )
        
    def _apply_final_formatting(self, html: str) -> str:
        """Apply final formatting including Instacart links and cleanup"""
        if not html.strip():
            return html
            
        # Replace Instacart links with branded buttons
        html = self._replace_instacart_links(html)
        
        # Clean up HTML (minimal for Django template compatibility)
        html = self._clean_email_html(html)
        
        # Encode non‑ASCII chars as numeric entities to avoid mojibake in strict clients
        try:
            html = self._encode_non_ascii_to_entities(html)
        except Exception:
            pass
        
        return html
    
    def _replace_instacart_links(self, html: str) -> str:
        """Replace Instacart links with branded CTA buttons"""
        soup = BeautifulSoup(html, "html.parser")
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "instacart.com" in href or "instacart.tools" in href or "instacart.tool" in href:
                btn_text = "Get Ingredients"
                cta_html = self._format_instacart_button(href, btn_text)
                a.replace_with(BeautifulSoup(cta_html, "html.parser"))
        
        return str(soup)
    
    def _clean_email_html(self, html: str) -> str:
        """Minimal HTML cleanup for Django template compatibility"""
        if not html.strip():
            return html
            
        # Remove extra whitespace but preserve structure
        html = re.sub(r'\n\s*\n', '\n', html)
        html = html.strip()
        
        return html

    def _encode_non_ascii_to_entities(self, html: str) -> str:
        """Convert all non‑ASCII characters to numeric HTML entities.

        This prevents smart quotes, en/em dashes, degree symbols, and other
        Unicode characters from rendering as replacement glyphs in email
        clients that mishandle charsets. Markup remains intact.
        """
        try:
            # Encode using ASCII with xmlcharrefreplace to emit e.g. &#8217;
            return html.encode('ascii', 'xmlcharrefreplace').decode('ascii')
        except Exception:
            return html
    
    def _create_fallback_django_body(self, raw_text: str) -> DjangoEmailBody:
        """Create a fallback Django body when OpenAI call fails"""
        
        # Simple content type detection
        content_type = "general_text"
        if any(word in raw_text.lower() for word in ['recipe', 'ingredients', 'cook']):
            content_type = "recipe"
        elif any(word in raw_text.lower() for word in ['shopping', 'grocery', 'buy']):
            content_type = "shopping_list"
        elif any(word in raw_text.lower() for word in ['meal plan', 'weekly', 'daily']):
            content_type = "meal_plan"
        
        # Create basic section
        section = ContentSection(
            title=None,
            content_type=content_type,
            format_type="paragraph",
            content=raw_text.replace('\n', '<br>'),
            priority=1,
            template_section="main"
        )
        
        # Create analysis
        analysis = ContentAnalysis(
            primary_content_type=content_type,
            has_structured_data=False,
            has_actionable_items=False,
            complexity_level="simple",
            recommended_organization="Single paragraph format"
        )
        
        # Create fallback HTML
        paragraphs = raw_text.split('\n\n')
        html_paragraphs = []
        for p in paragraphs:
            if p.strip():
                html_paragraphs.append(f"<p>{p.replace(chr(10), '<br>')}</p>")
        fallback_html = '\n'.join(html_paragraphs) if html_paragraphs else f"<p>{raw_text.replace(chr(10), '<br>')}</p>"
        
        return DjangoEmailBody(
            content_analysis=analysis,
            sections=[section],
            email_body_main=fallback_html,
            email_body_data="",
            email_body_final="",
            email_subject_suggestion=None,
            estimated_read_time=None
        )
    
    def _send_error_to_n8n(self, error: Exception, source: str):
        """Send error information to n8n webhook for tracking"""
        try:
            n8n_traceback_url = os.getenv('N8N_TRACEBACK_URL')
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(error),
                    "source": source,
                    "traceback": traceback.format_exc()
                })
        except Exception:
            # Silently fail if we can't send to n8n
            pass

    def _protect_urls(self, text: str) -> tuple[str, dict]:
        """Protect URLs with placeholders to prevent corruption"""
        url_pattern = r'https?://[^\s<>"\'()]+[^\s<>"\'.!?;,)]'
        urls = re.findall(url_pattern, text)
        url_placeholders = {}
        
        protected_text = text
        for i, url in enumerate(urls):
            placeholder = f"__URL_PLACEHOLDER_{i}__"
            url_placeholders[placeholder] = url
            protected_text = protected_text.replace(url, placeholder)
        
        return protected_text, url_placeholders

# Global dictionary to maintain guest state across request instances
GLOBAL_GUEST_STATE: Dict[str, Dict[str, Any]] = {}

# Default prompt templates in case they're not available in environment variables
DEFAULT_GUEST_PROMPT = """
<!-- =================================================================== -->
<!-- ===============  G U E S T   P R O M P T   T E M P L A T E  ======= -->
<!-- =================================================================== -->
<PromptTemplate id="guest" version="2025-06-13">
  <Identity>
    <Role>MJ, sautai's friendly meal‑planning consultant</Role>
    <Persona origin="Jamaica" raisedIn="Brooklyn, NY"
             traits="thoughtful, considerate, confident, food‑savvy"/>
  </Identity>

  <Mission>
    <Primary>
      Provide clear, accurate answers to food, nutrition, recipe and
      meal‑planning questions.
    </Primary>
    <Secondary>
      Suggest the next sensible step toward the user's cooking or health goal.
    </Secondary>
    <Scope>
      Guests have access only to general nutrition advice; no medical guidance.
    </Scope>
  </Mission>

  <Tone style="business‑casual" warmth="warm" approach="supportive" />

  <Guidelines>
    <OutputEfficiency>
      • Write in short paragraphs (≤ 4 sentences).  
      • Use bullet‑ or numbered‑lists for steps/options.  
      • Omit tool IDs and internal implementation details.  
    </OutputEfficiency>

    <GraphAndData>
      When quantitative data will aid understanding,  
      ① present a concise table **or** dataset snippet, then  
      ② describe (in one line) the graph that would best visualise it.  
      (If the runtime supports code‑execution, emit the plot; otherwise
      describe it clearly.)
    </GraphAndData>

    <FollowUp>
      Conclude most—but not every—turn with a brief invitation such as  
      "Anything else I can help you with?"
    </FollowUp>

    <Safety>
      Politely refuse any request outside food topics.  
      No medical, legal, or non‑food advice.
    </Safety>
    <Truthfulness>
      • Do not invent pantry items, IDs, quantities, or expiry dates. Use only
        data returned by tools you actually called (e.g., from
        <code>check_pantry_items</code> or <code>get_expiring_items</code>).  
      • If a requested action lacks a tool (e.g., deleting items), state this
        clearly and provide short manual guidance instead of claiming you can do it.
    </Truthfulness>
  </Guidelines>

  <Format>
    <Markdown>
      Render replies in **GitHub‑Flavored Markdown (GFM)** with headings, lists,
      and pipe tables for structured data. Avoid raw HTML unless asked.  
    </Markdown>
    <Tables>
      For weekly plans, use a table: `| Day | Breakfast | Lunch | Dinner |`.
    </Tables>
    <Dates>
      Format ranges like `Mon–Sun, Sep 8–14, 2025` (en dash, proper spacing).
    </Dates>
  </Format>

  <ExampleFormat>
    <Paragraph>An answer introduction …</Paragraph>
    <Bullets>
      <Item>Key point 1</Item>
      <Item>Key point 2</Item>
      <Item>Key point 3</Item>
    </Bullets>
    <OptionalInvite>Anything else I can help you with?</OptionalInvite>
  </ExampleFormat>
</PromptTemplate>
"""

DEFAULT_AUTH_PROMPT = """
<!-- ==================  S A U T A I   A S S I S T A N T   ================== -->
<!--  Runs on: gpt-5 (primary) | gpt-o4-mini (fallback)                     -->
<!--  Version: 2025-07-03                                                   -->
<PromptTemplate id="authenticated" version="2025-07-03">

  <!-- ───── 1. IDENTITY ───── -->
  <Identity>
    <Role>MJ — sautai's friendly meal-planning consultant</Role>
    <Persona origin="Jamaica"
             raisedIn="Brooklyn, NY"
             traits="thoughtful, considerate, confident, food-savvy"/>
    <User name="{username}" />
  </Identity>

  <!-- ───── 2. CONTEXT ───── -->
  <Context>
    <RecentConversation>{user_chat_summary}</RecentConversation>
    <Personalization>{user_ctx}</Personalization>
    <AdminNotice revealOnce="true">{admin_section}</AdminNotice>
  </Context>

  <!-- ───── 3. MISSION ───── -->
  <Mission>
    <Primary>
      • Answer food, nutrition, recipe, and meal-planning questions.  
      • Suggest actionable next steps and proactive follow-ups.  
    </Primary>
    <ConnectWithChefs>
      Match users with **local chefs** so they save time and eat better.
    </ConnectWithChefs>
  </Mission>

  <!-- ───── 4. CAPABILITIES (TOOLS) ───── -->
  <Capabilities>
    The assistant is limited to the following registered tools for this session.
    You may not imply actions beyond these tools. When suggesting next steps,
    prefer using one of these tools; otherwise clearly explain the limitation and
    offer concise manual guidance.

{all_tools}
  </Capabilities>

  <!-- ───── 5. OPERATING INSTRUCTIONS ───── -->
  <OperatingInstructions>

    <!-- 5-A. TOOL USAGE RULES -->
    <Tools>
      <Rule>Invoke tools whenever they materially improve the answer.</Rule>
      <Bundling>Batch related tool calls in one turn when feasible.</Bundling>

      <!-- Meal-plan management -->
      <MealPlans>
        • Use <code>list_user_meal_plans</code> before guessing.  
        • Remind users to approve pending plans before creating new ones.  
        • Respect week context via <code>get_current_date</code>,
          <code>adjust_week_shift</code>, <code>reset_current_week</code>.  
        • Create plans with <code>create_meal_plan</code> then swap meals
          via <code>replace_meal_plan_meal</code> when mixing AI & chef meals.  

        <!-- STRICT: Meal‑plan edits must use tools -->
        <MealPlanEdits>
          • If the user asks to “change/replace/swap” a meal, or says they
            “don’t have/missing” an ingredient and wants an alternative, you
            MUST call tools to update the actual meal plan — do not reply with
            a standalone recipe instead of changing the plan.  
          • Preferred flow:
            1) Call <code>list_user_meal_plans</code> and pick the most recent plan.  
            2) If day and meal_type are explicit (e.g., “Monday breakfast”), call
               <code>modify_meal_plan</code> with those fields and the user_prompt.  
            3) If the slot is ambiguous, call <code>get_meal_plan_meals_info</code>
               to identify candidates, ask ONE short clarifying question, then
               call <code>modify_meal_plan</code>.  
          • Keep confirmations brief and structured; prioritize the tool call(s)
            and a compact summary of the changed slot(s).
        </MealPlanEdits>
      </MealPlans>

      <!-- Macro-nutrients & media -->
      <MealPlanPrepping>
        • To fetch accurate macros for a meal, call
          <code>get_meal_macro_info</code> with a specific <code>meal_id</code>.  
        • To surface a cooking tutorial on request, call
          <code>find_related_youtube_videos</code> with a <code>meal_id</code>.  
      </MealPlanPrepping>

      <!-- Pantry & shopping -->
      <PantryManagement>
        • Once per week suggest a pantry audit, highlighting environmental,
          financial, and health benefits of minimizing waste.  
        • Never invent pantry inventory, IDs, quantities, or expiry dates. Only
          report items returned by tools such as <code>check_pantry_items</code>
          and <code>get_expiring_items</code>.
        • If a requested action has no tool (e.g., deleting pantry items), say so
          explicitly and offer concise manual steps. Do not fabricate app‑specific
          flows, IDs, or confirmations.
      </PantryManagement>
      <Instacart>
        • Provide shopping links using <code>generate_instacart_link_tool</code>.
          Note US/Canada availability if user locale ≠ US/CA.  
      </Instacart>

      <!-- Payments -->
      <PaymentLinks>
        • Stripe links must be full, valid URLs.  
      </PaymentLinks>
    </Tools>

    <!-- 5-B. OUTPUT & STYLE -->
    <Format>
      <Markdown>
        Render answers in **GitHub‑Flavored Markdown (GFM)**.  
        • Use headings (##), paragraphs, and bulleted/numbered lists.  
        • For structured content (meal plans, comparisons), use **GFM pipe tables**.  
        • Avoid raw HTML unless explicitly requested.
      </Markdown>
      <Tables>
        For weekly meal plans, output a compact GFM table with columns:  
        `| Day | Breakfast | Lunch | Dinner |`.  
        Keep entries concise; use line breaks within a cell only when necessary.
      </Tables>
      <Dates>
        Format date ranges as: `Mon–Sun, Sep 8–14, 2025` (en dash).  
        Always include appropriate spaces; never run words together.
      </Dates>
      <Paragraph maxSentences="3-4"/>
      <Lists>Use bulleted or numbered lists where logical.</Lists>
      <Data>
        When numbers matter, return **both**  
        ① a concise table and  
        ② either an in-context graph (if runtime supports) **or** a one-line
           description of the ideal visual.  
        Use light formats (small PNG, SVG, or summarized JSON).  
      </Data>
      <FollowUp>
        End most replies with a brief invitation or a creative suggestion
        (e.g., pantry audit, local chef collab).  
      </FollowUp>
    </Format>

    <!-- 5-C. SAFETY & SCOPE -->
    <Safety>
      Provide general nutrition guidance only — no medical advice.  
      Politely decline off-topic or unsafe requests.  
    </Safety>

    <!-- 5-D. TOKEN BUDGET GUIDANCE -->
    <TokenBudget>
      • Target ≤ 600 tokens/completion for gpt-o4-mini compatibility.  
      • Omit unnecessary repetition; prioritize tool calls over long prose.  
    </TokenBudget>

  </OperatingInstructions>
</PromptTemplate>
"""

# Get template from environment, fallback to defaults if not available
GUEST_PROMPT_TEMPLATE = DEFAULT_GUEST_PROMPT
AUTH_PROMPT_TEMPLATE = DEFAULT_AUTH_PROMPT

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────────────
#  Constants
# ───────────────────────────────────────────────────────────────────────────────
# Default fallback models if model selection fails
MODEL_AUTH_FALLBACK = "gpt-5-mini"
MODEL_GUEST_FALLBACK = "gpt-5-nano"

#  ▸ A < 50‑token teaser shown to guests every turn
TOOL_TEASER = (
    "- create_meal_plan: build and manage a weekly plan\n"
    "- list_upcoming_meals: see what's next\n"
    "- …and 20 more when you sign up! As well as having your own personal sautai assistant."
)


# ───────────────────────────────────────────────────────────────────────────────
#  Assistant class
# ───────────────────────────────────────────────────────────────────────────────
class MealPlanningAssistant:
    """sautai meal‑planning assistant with guest/auth modes and parallel‑tool support."""

    def __init__(self, user_id: Optional[Union[int, str]] = None):
        self.client = OpenAI(api_key=settings.OPENAI_KEY)
        # Better detection of numeric user IDs (authenticated users)
        if user_id is not None:
            if isinstance(user_id, numbers.Number) or (isinstance(user_id, str) and user_id.isdigit()):
                self.user_id = int(user_id)
            elif isinstance(user_id, str) and user_id:
                # Keep provided string user_id (guest_id from session or request)
                # Strip any "guest:" prefix for consistency if it exists
                self.user_id = user_id.replace("guest:", "") if user_id.startswith("guest:") else user_id
            else:
                # Only generate a new one if None or empty string provided
                self.user_id = generate_guest_id()
        else:
            self.user_id = generate_guest_id()
            
        # Don't cache tools - load them fresh each time to pick up changes
        # self.auth_tools and self.guest_tools are loaded in _get_tools_for_user()
        
        # Initialize Django Template Email Formatter
        self._django_email_formatter = DjangoTemplateEmailFormatter(self.client)
        
        self.system_message = (
            "You are sautai's helpful meal‑planning assistant. "
            "Answer questions about food, nutrition and meal plans."
        )

        # Track function_calls that don't yet have matching outputs.
        # We keep each orphaned call exactly one extra turn so the model
        # can see the output and avoid repeating questions.
        self._pending_calls: Dict[str, Dict[str, Any]] = {}
        
        # Log initialization details
        is_guest = self._is_guest(self.user_id)
        # Streaming debug toggle (env or Django DEBUG)
        try:
            self._stream_debug = os.getenv('ASSISTANT_STREAM_DEBUG', '').lower() in ('1','true','yes','on') or getattr(settings, 'DEBUG', False)
        except Exception:
            self._stream_debug = False

    def _dbg(self, msg: str):
        if getattr(self, '_stream_debug', False):
            try:
                logger.info(f"STREAMDEBUG: {msg}")
            except Exception:
                pass

    # ───────────────────────────────────────── schema utils (adapter)
    def _clean_schema_for_openai(self, schema: dict) -> dict:
        """Adapter so callers on this class can clean Pydantic JSON Schema for
        OpenAI Responses 'json_schema' formatting. Delegates to the formatter's
        implementation and falls back to a local cleaner if needed.
        """
        try:
            # Reuse the formatter's implementation
            return self._django_email_formatter._clean_schema_for_openai(schema)
        except Exception:
            # Minimal fallback copy (kept simple to avoid import cycles)
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

    # ───────────────────────────────────────── helper: persist guest state
    def _store_guest_state(self, response_id: str, history: list) -> None:
        """
        Save the latest `response_id` together with the full conversation
        history so the next HTTP request can rebuild context instead of
        starting the onboarding over.
        """
        GLOBAL_GUEST_STATE[self.user_id] = {
            "response_id": response_id,
            "history": history,
        }

    def _get_tools_for_user(self, is_guest: bool) -> List[Dict[str, Any]]:
        """Load tools fresh each time to pick up any code changes."""
        if is_guest:
            tools = get_all_guest_tools()
        else:
            tools = [t for t in get_all_tools() if not t["name"].startswith("guest")]
        

        
        return tools

    # ─────────────────────────────────────────  public entry points
    def send_message(
        self, message: str, thread_id: Optional[str] = None # Not used for auth users anymore
    ) -> Dict[str, Any]:
        """Send a message using database-backed history (non-streaming)."""
        is_guest = self._is_guest(self.user_id)
        
        # 🔍 DIAGNOSTIC: Log input to OpenAI
        input_preview = repr(message[:300])
        logger.info(f"INPUT TO OPENAI: {input_preview}")
        
        if any(header in message for header in ['From:', 'Date:', 'Subject:']):
            logger.warning(f"⚠️ HEADERS IN OPENAI INPUT: {input_preview}")
        
        # Select the appropriate model based on user status and message complexity
        model = choose_model(
            user_id=self.user_id,
            is_guest=is_guest,
            question=message
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_GUEST_FALLBACK if is_guest else MODEL_AUTH_FALLBACK

        # For guests, use in-memory history if available
        if is_guest:
            guest_data = GLOBAL_GUEST_STATE.get(self.user_id, {})
            if guest_data and "history" in guest_data:
                # Get existing history and append new message
                history = guest_data["history"].copy()
                history.append({"role": "user", "content": message})
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
            
            prev_resp_id = guest_data.get("response_id")
            chat_thread = None
        else:
            # For auth users, load history from DB
            chat_thread = self._get_or_create_thread(self.user_id)
            history = chat_thread.openai_input_history or []
            if not history:
                 history.append({"role": "system", "content": self.system_message})
            history.append({"role": "user", "content": message})
            # Truncate history to prevent context length exceeded errors
            history = self._truncate_history_if_needed(history, max_messages=30, max_tokens=25000)
            prev_resp_id = None # Send full history


        current_history = history.copy()
        final_response_id = None
        
        # Handle tool calls in a loop until we get a final response
        while True:
            try:
                resp = self.client.responses.create(
                    model=model,
                    input=current_history,
                    instructions=self._instructions(is_guest),
                    tools=self._get_tools_for_user(is_guest),
                    parallel_tool_calls=True,
                    previous_response_id=prev_resp_id, 
                )
                
                final_response_id = resp.id                
                # Check for tool calls in response
                tool_calls_in_response = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
                
                # Extract any text response
                response_text = self._extract(resp)
                print(f"Response text: {response_text}")
                
                # If there's text content, add it to history
                if response_text:
                    current_history.append({"role": "assistant", "content": response_text})
                
                # If no tool calls, we're done
                if not tool_calls_in_response:
                    print("No tool calls found, finishing response")
                    break
                
                print(f"Found {len(tool_calls_in_response)} tool calls to execute")
                
                # Execute all tool calls
                for tool_call_item in tool_calls_in_response:
                    call_id = getattr(tool_call_item, 'call_id', None)
                    name = getattr(tool_call_item, 'name', None)
                    arguments = getattr(tool_call_item, 'arguments', '{}')
                    
                    print(f"Executing tool call: {name} with call_id: {call_id}")
                    
                    # Fix user_id in arguments if needed
                    fixed_args = self._fix_function_args(name, arguments)
                    if fixed_args != arguments:
                        print(f"Fixed user_id in arguments: {arguments} -> {fixed_args}")
                        arguments = fixed_args
                    
                    # Add function call to history
                    current_history.append({
                        "type": "function_call",
                        "name": name,
                        "arguments": arguments,
                        "call_id": call_id
                    })
                    
                    try:
                        # Create a tool call object that handle_tool_call expects
                        tool_call_obj = type("Call", (), {
                            "call_id": call_id,
                            "function": type("F", (), {
                                "name": name,
                                "arguments": arguments
                            })
                        })
                        
                        # Execute the tool call
                        from .tool_registration import handle_tool_call
                        result = handle_tool_call(tool_call_obj)
                        print(f"Tool call result: {result}")
                        
                    except Exception as e:
                        print(f"Error executing tool call {name}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        result = {"status": "error", "message": str(e)}
                    
                    # Add function result to history
                    current_history.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result)
                    })
                
                # Continue the loop with updated history to get final response
                prev_resp_id = final_response_id
                print(f"Continuing with updated history, previous_response_id={prev_resp_id}")
                
            except Exception as e:
                logger.error(f"Error in send_message loop: {str(e)}")
                traceback.print_exc()
                return {"status": "error", "message": f"An error occurred: {str(e)}"}
        
        # Get the final response text
        final_output_text = response_text
        
        # 🔍 DIAGNOSTIC: Log raw OpenAI response
        response_preview = repr(final_output_text[:500]) if final_output_text else "''"
        logger.info(f"RAW OPENAI RESPONSE: {response_preview}")
        
        if final_output_text and any(header in final_output_text for header in ['From:', 'Date:', 'Subject:']):
            logger.warning(f"⚠️ HEADERS IN OPENAI RESPONSE: {response_preview}")

        final_history = current_history
        
        # Persist the final state
        if not is_guest:
            self._persist_state(self.user_id, final_response_id, is_guest, final_history)
            # Also save the user message and response text in UserMessage model
            if chat_thread:
                self._save_turn(self.user_id, message, final_output_text, chat_thread)
        elif is_guest:
            # Persist guest state (keeps plain text + response_id)
            self._store_guest_state(final_response_id, final_history)

        # 🔍 DIAGNOSTIC: Log after formatting
        if hasattr(self, '_format_text_for_email_body'):
            formatted_response = self._format_text_for_email_body(final_output_text)
            formatted_preview = repr(formatted_response[:500])
            logger.info(f"AFTER FORMATTING: {formatted_preview}")
            
            if any(header in formatted_response for header in ['From:', 'Date:', 'Subject:']):
                logger.warning(f"⚠️ HEADERS AFTER FORMATTING: {formatted_preview}")

        return {
            "status": "success",
            "message": final_output_text,
            "response_id": final_response_id,
        }

    def stream_message(
        self, message: str, thread_id: Optional[str] = None # thread_id is the DB ChatThread ID, not OpenAI's
    ) -> Generator[Dict[str, Any], None, None]:

        """Stream a message using database-backed history."""
        is_guest = self._is_guest(self.user_id)
        
        # Select the appropriate model based on user status and message complexity
        model = choose_model(
            user_id=self.user_id,
            is_guest=is_guest,
            question=message
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_GUEST_FALLBACK if is_guest else MODEL_AUTH_FALLBACK

        # For guests, use in-memory history if available
        if is_guest:
            guest_data = GLOBAL_GUEST_STATE.get(self.user_id, {})
            if guest_data and "history" in guest_data:
                # Get existing history and append new message
                history = guest_data["history"].copy()
                history.append({"role": "user", "content": message})
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
            
            # Guest state might still use previous_response_id for short-term continuity
            prev_resp_id = guest_data.get("response_id")
            chat_thread = None
            user_msg = None
        else:
            # For auth users, load history from DB
            chat_thread = self._get_or_create_thread(self.user_id)
            history = chat_thread.openai_input_history or [] # Load history
            if not history: # If history is empty, initialize with system message
                 history.append({"role": "system", "content": self.system_message})
            history.append({"role": "user", "content": message}) # Add current message
            # Truncate history to prevent context length exceeded errors
            history = self._truncate_history_if_needed(history, max_messages=30, max_tokens=25000)
            prev_resp_id = None # We send full history, so no previous_response_id needed
            user_msg = (
                 self._save_user_message(self.user_id, message, chat_thread) if chat_thread else None
            )
        
        
        yield from self._process_stream(
            model=model,
            history=history, # Send the loaded/updated history
            instructions=self._instructions(is_guest),
            tools=self._get_tools_for_user(is_guest),
            previous_response_id=prev_resp_id, # Set to None for auth users
            user_id=self.user_id,
            is_guest=is_guest,
            chat_thread=chat_thread, # Pass thread for saving later
            user_msg=user_msg,
        )

    # ─────────────────────────────────────────  core streaming logic
    def _process_stream(
        self,
        *,
        model: str,
        history: List[Dict[str, Any]],
        instructions: str,
        tools: List[Dict[str, Any]],
        previous_response_id: Optional[str],
        user_id: int,
        is_guest: bool,
        chat_thread: Optional[ChatThread],
        user_msg: Optional[UserMessage],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams one assistant turn, handles parallel tool calls by:
          - yielding text and function_call events as they arrive
          - appending both the function_call and its output into `history`
          - looping back so the model can continue with that new context.
        """
        
        
        # If previous_response_id is None and this is a guest, try to fetch from cache
        if previous_response_id is None and is_guest:
            prev_resp_id = get(f"last_resp:{self.user_id}")
            if prev_resp_id:
                previous_response_id = prev_resp_id
        
        start_ts = time.time()
        current_history = history[:] # Work on a copy
        final_response_id = None # Track the final OpenAI response ID
        loop_iteration = 0
        max_iterations = 10  # Prevent infinite loops

        while True:
            loop_iteration += 1
            
            # Safety check to prevent infinite loops
            if loop_iteration > max_iterations:
                yield {"type": "response.completed"}
                break
            
            # 1) Start streaming from the Responses API
            # for i, item in enumerate(current_history):
            #     item_type = item.get('type') or item.get('role', 'unknown')
            
            
            # Truncate history before each API call to prevent context length issues
            current_history = self._truncate_history_if_needed(current_history, max_messages=30, max_tokens=25000)
            # Validate and clean history before sending to OpenAI
            current_history = self._validate_and_clean_history(current_history)
            
            stream = self.client.responses.create(
                model=model,
                input=current_history, # Use the current history copy
                instructions=instructions,
                tools=tools,
                previous_response_id=previous_response_id,
                stream=True,
                parallel_tool_calls=True,
            )

            new_id = None
            buf = ""
            sent_text_delta = False  # Track if we emitted any incremental text
            calls: List[Dict[str, Any]] = []
            wrapper_to_call: Dict[str, str] = {}
            latest_id_in_stream = previous_response_id # Initialize with previous ID
            response_completed = False
            self._dbg(f"turn_start user={self.user_id} prev_id={previous_response_id} model={model}")

            # 2) Consume the event stream
            for ev in stream:
                # 2a) Capture the new response ID
                if isinstance(ev, ResponseCreatedEvent):
                    new_id = ev.response.id
                    latest_id_in_stream = new_id # Always update with the latest ID
                    final_response_id = new_id # Track the latest ID received
                    yield {"type": "response_id", "id": new_id}
                    self._dbg(f"response_created id={new_id}")
                    continue

                # 2b) End of this assistant turn
                if isinstance(ev, ResponseCompletedEvent):
                    response_completed = True
                    break

                # 2c) Stream text deltas
                if isinstance(ev, ResponseTextDeltaEvent):
                    if ev.delta:
                        # Append and emit only the new delta
                        buf += ev.delta
                        sent_text_delta = True
                        yield {"type": "text", "content": ev.delta}
                        if len(buf) % 200 == 0:
                            self._dbg(f"delta_progress chars={len(buf)}")
                    continue
                if isinstance(ev, ResponseTextDoneEvent):
                    # If no deltas were emitted (rare), emit the final text once
                    if ev.text and not sent_text_delta:
                        buf = ev.text
                        sent_text_delta = True
                        yield {"type": "text", "content": ev.text}
                    # Otherwise, do not re-emit full text to avoid duplication
                    continue

                # 2d) Function‑call argument fragments
                if isinstance(ev, ResponseFunctionCallArgumentsDeltaEvent):
                    # Map wrapper_id → real call_id if we haven't yet
                    if ev.item_id not in wrapper_to_call and getattr(ev, "item", None):
                        cid = getattr(ev.item, "call_id", None)
                        if cid:
                            wrapper_to_call[ev.item_id] = cid
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)

                    # Accumulate arguments
                    tgt = next((c for c in calls if c["id"] == real_id), None)
                    if not tgt:
                        tgt = {"id": real_id, "name": None, "args": ""}
                        calls.append(tgt)
                    tgt["args"] += ev.delta
                    continue

                # 2e) End‑of‑args: emit function_call and append to history
                if isinstance(ev, ResponseFunctionCallArgumentsDoneEvent):
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)
                    entry = next((c for c in calls if c["id"] == real_id), None)
                    if not entry:
                        continue

                    args_json = entry["args"]
                    args_obj  = json.loads(args_json)
                    
                    
                    # Fix the user_id in the arguments if needed
                    fixed_args_json = self._fix_function_args(entry["name"], args_json)
                    if fixed_args_json != args_json:
                        args_json = fixed_args_json
                        args_obj = json.loads(args_json)
                    
                    # 1) Tell front‑end the call is happening
                    yield {
                        "type": "response.function_call",
                        "name": entry["name"],
                        "arguments": args_obj,
                        "call_id": real_id,
                    }

                    # 2) Inject the function_call into CURRENT history
                    call_entry = {
                        "type":       "function_call",
                        "name":       entry["name"],
                        "arguments":  args_json,
                        "call_id":    real_id
                    }
                    current_history.append(call_entry)
                    # Removed cache logic
                    continue

                # 2f) Wrapper event: new function_call header
                if isinstance(ev, ResponseOutputItemAddedEvent) and isinstance(ev.item, ResponseFunctionToolCall):
                    item       = ev.item
                    wrapper_id = item.id
                    call_id    = item.call_id
                    name       = item.name

                    wrapper_to_call[wrapper_id] = call_id
                    calls.append({"id": call_id, "name": name, "args": ""})

                    yield {
                        "type":        "response.tool",
                        "tool_call_id": call_id,
                        "name":        name,
                        "output":      None,
                    }
                    continue

                # 2g) Other output items – ignore
                if isinstance(ev, ResponseOutputItemDoneEvent):
                    continue

            # 3) Flush any buffered text
            if buf:
                # Only flush text if we never emitted deltas (fallback case)
                if not sent_text_delta:
                    yield {"type": "text", "content": buf}

                # Also persist the assistant's reply into the running history
                current_history.append({
                    "role": "assistant",
                    "content": buf.strip()
                })
                
                # 3a) Shape the final content into strict GFM for the frontend
                shaped = None
                try:
                    shaped = self._shape_chat_markdown(buf)
                except Exception as e:
                    # Absolute fallback to ensure frontend always receives a render payload
                    shaped = {"markdown": buf}
                md_len = len((shaped or {}).get('markdown', '') or '')
                self._dbg(f"render_ready len={md_len} deltas={sent_text_delta}")
                # Emit as a tool_result for compatibility with existing SSE mapping
                yield {
                    "type": "tool_result",
                    "tool_call_id": "render_1",
                    "name": "response.render",
                    "output": shaped,
                }
                
            # Store the final response ID in Redis for this user (expires in 24h)
            if final_response_id:
                set(f"last_resp:{self.user_id}", final_response_id, 86400)

            # 4) If response was completed and we have text content, break the loop
            # This is the key fix - if response completed and we have text, we're done
            if response_completed and buf:
                # ── persist the assistant turn for guests ───────────────
                # Note: assistant message already added to history in step 3, don't duplicate
                if is_guest and final_response_id:
                    self._store_guest_state(final_response_id,
                                            current_history)
                yield {"type": "response.completed"}
                self._dbg(f"turn_end completed=1 len={len(buf)} calls={len(calls)} id={final_response_id}")
                break
            
            # 4.1) If no function calls were requested, finish up
            
            if not calls:
                yield {"type": "response.completed"}
                self._dbg(f"turn_end no_calls len={len(buf)} id={final_response_id}")
                break # Exit the while loop
            
            # 4.2) If response was completed but there are function calls, we need to handle them first
            # If response was completed and no function calls, we should have already broken above
            if response_completed and not calls:
                yield {"type": "response.completed"}
                break

            # 5) Drop any stray wrapper‑only entries
            calls = [c for c in calls if not c["id"].startswith("fc_")]
            
            # 5.1) If response was completed and we have no function calls after filtering, break
            if response_completed and not calls:
                yield {"type": "response.completed"}
                break

            # 6) Execute all parallel calls
            for call in calls:
                call_id = call["id"]
                
                
                args_obj = json.loads(call["args"] or "{}")
                
                # Fix the user_id in the arguments if needed
                fixed_args_json = self._fix_function_args(call["name"], call["args"] or "{}")
                if fixed_args_json != (call["args"] or "{}"):
                    args_obj = json.loads(fixed_args_json)
                
                try:
                    
                    # Time the tool execution
                    tool_start_time = time.time()
                    result = handle_tool_call(
                        type("Call", (), {
                            "call_id": call_id,
                            "function": type("F", (), {
                                "name": call["name"],
                                "arguments": json.dumps(args_obj)
                            })
                        })
                    )
                    tool_execution_time = time.time() - tool_start_time
                    
                        
                except Exception as e:
                    #n8n traceback
                    n8n_traceback = {
                        'error': str(e),
                        'source': 'tool_call',
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                    result = {"status": "error", "message": str(e)}

                # Emit tool_result
                yield {
                    "type":        "tool_result",
                    "tool_call_id": call_id,
                    "name":        call["name"],
                    "output":      result,
                }

                # If this tool modifies the meal plan, emit a final render payload to update the UI
                try:
                    if call["name"] in ("modify_meal_plan", "replace_meal_plan_meal"):
                        md = None
                        if isinstance(result, dict) and result.get("status") == "success":
                            meals = result.get("meals") or []
                            tgt_day = result.get("target_day")
                            tgt_type = result.get("target_meal_type")
                            # Prefer to render only the targeted slot(s) when known
                            subset = [m for m in meals if (not tgt_day or m.get("day") == tgt_day) and (not tgt_type or m.get("meal_type") == tgt_type)]
                            rows = subset if subset else meals
                            # Build a small GFM summary table
                            lines = ["### Meal Plan Updated", "", "| Day | Meal Type | Meal |", "| --- | --- | --- |"]
                            for m in rows[:12]:  # cap to avoid giant payloads
                                lines.append(f"| {m.get('day','?')} | {m.get('meal_type','?')} | {m.get('meal_name','?')} |")
                            md = "\n".join(lines)
                        if md:
                            shaped = {"markdown": md}
                            yield {
                                "type":        "tool_result",
                                "tool_call_id": f"render_after_{call_id}",
                                "name":        "response.render",
                                "output":      shaped,
                            }
                except Exception:
                    pass

                # 7a) Inject the function_call_output into CURRENT history
                result_json = _safe_json_dumps(result)
                output_entry = {
                    "type":     "function_call_output",
                    "call_id":  call_id,
                    "output":   result_json,
                }
                current_history.append(output_entry)
                # Removed cache logic

            # Debug: Print the history being sent to the next request
            for i, item in enumerate(current_history):
                item_type = item.get("type", item.get("role", "unknown"))

            # 7b) If we had text AND function calls in the same response, we're done
            # Don't make another API call as this was a complete response
            if buf and calls:
                # Persist the final state before breaking
                if is_guest and final_response_id:
                    self._store_guest_state(final_response_id, current_history)
                yield {"type": "response.completed"}
                break

            # 8) Loop back: Prepare for the next API call within the same turn
            previous_response_id = latest_id_in_stream # Use the ID from the segment just processed
            # IMPORTANT: We continue the loop, sending the *updated* current_history

        # --- End of while loop ---
        
        processing_time = time.time() - start_ts
        
        # Persist the *final* state after the loop completes
        if not is_guest and final_response_id:
             # Pass the final history state and the final response ID
            self._persist_state(user_id, final_response_id, is_guest, current_history)
        elif is_guest and final_response_id:
             # Update guest state with final ID
             self._store_guest_state(final_response_id, current_history)

    # ────────────────────────────────────────────────────────────────────
    #  Prompt helpers
    # ────────────────────────────────────────────────────────────────────
    def build_prompt(self, is_guest: bool) -> str:
        """
        Build the system prompt for the assistant based on whether the user is a guest or authenticated
        """
        all_tools = self._get_tools_for_user(is_guest)
        if is_guest:
            guest_tools = self._get_tools_for_user(is_guest)
            return GUEST_PROMPT_TEMPLATE.format(
                guest_tools=self._summarize_tools_for_prompt(guest_tools),
                all_tools=self._summarize_tools_for_prompt(all_tools)
            )
        else:
            user = None
            try:
                user = CustomUser.objects.get(id=self.user_id)
                user_ctx = generate_user_context(user)
                username = user.username
                admin_blurb = self._current_admin_blurb(user)
                admin_section = ""
                if admin_blurb:
                    admin_section = f"\nWEEKLY UPDATE\n{admin_blurb}\n\n"
                    admin_section += "Make sure to subtly acknowledge this announcement information early in the conversation. Only mention once per entire conversation and only if it's natural in the context. Do not prefix with 'Weekly Update'.\n\n"
                
                # Get the user's chat summary if available
                user_chat_summary = self._get_user_chat_summary(user)
                
                # Generate information about local chefs and meal events
                local_chef_and_meal_events = self._local_chef_and_meal_events(user)
                
                # Get user's preferred language for instructions
                user_preferred_language = _get_language_name(getattr(user, 'preferred_language', 'en'))
                language_instruction = ""
                if user_preferred_language and user_preferred_language.lower() != 'en':
                    language_name = _get_language_name(user_preferred_language)
                    language_instruction = f"\n#LANGUAGE PREFERENCE\nThis user's preferred language is {language_name}. Please respond in {language_name} unless the user specifically requests English or another language.\n\n"
                
                # Ensure AUTH_PROMPT_TEMPLATE has placeholders for all these values
                # Example: {username}, {user_ctx}, {admin_section}, {all_tools}, {user_chat_summary}, {local_chef_and_meal_events}
                prompt = AUTH_PROMPT_TEMPLATE.format(
                    username=username,
                    user_ctx=user_ctx,
                    admin_section=admin_section,
                    all_tools=self._summarize_tools_for_prompt(self._get_tools_for_user(is_guest)),
                    user_chat_summary=user_chat_summary,
                    local_chef_and_meal_events=local_chef_and_meal_events
                )
                
                # Add language instruction if needed
                return prompt + language_instruction
            except CustomUser.DoesNotExist:
                logger.warning(f"User with ID {self.user_id} not found while building prompt. Using fallback.")
                return f"You are MJ, sautai's friendly meal-planning consultant. You are currently experiencing issues with your setup and functionality. You cannot help with any of the user's requests at the moment but please let them know the sautai team has been notified and will look into it as soon as possible."
            except Exception as e:
                logger.error(f"Error generating prompt for user {self.user_id}: {str(e)}")
                # Return a simple fallback prompt
                username_str = user.username if user else f"user ID {self.user_id}"
                return f"You are MJ, sautai's friendly meal-planning consultant. You are currently chatting with {username_str} and experiencing issues with your setup and functionality. You cannot help with any of the user's requests at the moment but please let them know the sautai team has been notified and will look into it as soon as possible."

    def _instructions(self, is_guest: bool) -> str:
        """
        Return the system‑prompt string that steers GPT for this turn.
        We keep two variants: a lightweight guest prompt and a fuller
        authenticated‑user prompt.  Both are < 350 tokens.
        """
        return self.build_prompt(is_guest)

    def _summarize_tools_for_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Render a concise, friendly list of available tools for the prompt.

        Example output:
          • create_meal_plan — Create a weekly meal plan for a user
          • modify_meal_plan — Modify a specific slot in a plan
        """
        try:
            lines: List[str] = []
            for t in tools or []:
                name = t.get("name", "unknown_tool")
                desc = (t.get("description") or "").strip()
                if desc:
                    # keep it to one line, ~90 chars max
                    if len(desc) > 90:
                        desc = desc[:87].rstrip() + "…"
                    lines.append(f"  • {name} — {desc}")
                else:
                    lines.append(f"  • {name}")
            return "\n".join(lines) if lines else "  • (no tools registered)"
        except Exception:
            # Never break prompt building on summarization
            try:
                return "\n".join([f"  • {t.get('name','unknown_tool')}" for t in tools or []])
            except Exception:
                return "  • (tools unavailable)"

    # ────────────────────────────────────────────────────────────────────
    #  Conversation‑reset helper
    # ────────────────────────────────────────────────────────────────────
    def reset_conversation(self) -> Dict[str, Any]:
        """
        Clears conversation state so the next message starts a brand‑new thread.

        * Guests → removes their entry from the in‑memory dict.
        * Auth users → marks all active ChatThread rows inactive in a single
          bulk‑update (cheap DB call).
        """
        if self._is_guest(self.user_id):
            # Safely drop the key; dict.pop(k, None) returns None if missing.
            GLOBAL_GUEST_STATE.pop(self.user_id, None)
            return {"status": "success", "message": "Guest context cleared."}

        # Authenticated user: bulk‑update threads instead of iterating row‑by‑row.
        try:
            user = CustomUser.objects.get(id=self.user_id)
        except CustomUser.DoesNotExist:
            return {"status": "error", "message": "User not found."}

        ChatThread.objects.filter(user=user, is_active=True).update(is_active=False)
        return {"status": "success", "message": "Conversation reset for user."}
    
    # ────────────────────────────────────────────────────────────────────
    #  DB + state helpers
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_guest(user_id) -> bool:
        # only strings can startwith()
        if isinstance(user_id, str):
            return user_id.startswith("guest_") or user_id == "guest"
        # everything else (ints, UUIDs, etc.) is an auth user
        return False

    def _persist_state(self, user_id: int, resp_id: str, is_guest: bool, history: List[Dict[str, Any]]) -> None:
        """Persist the final response ID and the full conversation history to the DB for auth users, or update guest state."""
        if is_guest:
            # Store both response_id and history for guests
            self._store_guest_state(resp_id, history)
            print(f"GUEST_HISTORY: Persisted conversation with {len(history)} messages")
        else:
            try:
                thread = self._get_or_create_thread(user_id)
                
                # Store as a list to ensure proper lookup
                if isinstance(thread.openai_thread_id, list):
                    thread.openai_thread_id.append(resp_id)
                else:
                    # If it's a string or None, create a new list
                    old_value = thread.openai_thread_id
                    thread.openai_thread_id = [resp_id]
                
                # Also update latest_response_id for reference
                thread.latest_response_id = resp_id
                thread.openai_input_history = history # Save the complete history
                
                # Mark announcement as shown (if we included one)
                today = timezone.localdate()
                user = CustomUser.objects.get(id=user_id)
                admin_blurb = self._current_admin_blurb(user)
                if admin_blurb and not thread.announcement_shown:
                    thread.announcement_shown = today
                
                thread.save()
            except Exception as e:
                logger.error(f"Failed to persist state for user {user_id}: {str(e)}")
                traceback.print_exc()

    # ── Thread & message helpers
    def _get_or_create_thread(self, user_id: int) -> ChatThread:
        user = CustomUser.objects.get(id=user_id)
        try:
            thread = ChatThread.objects.filter(user=user, is_active=True).latest("created_at")
            
            # Log the thread ID and openai_thread_id for debugging
            if thread:
                thread_id = thread.id
                openai_id = thread.openai_thread_id
                latest_id = thread.latest_response_id
            return thread
            
        except ChatThread.DoesNotExist:
            new_thread = ChatThread.objects.create(user=user, is_active=True, openai_thread_id=[])
            return new_thread

    @staticmethod
    def _save_user_message(user_id: int, txt: str, thread: ChatThread) -> UserMessage:
        user = CustomUser.objects.get(id=user_id)
        return UserMessage.objects.create(thread=thread, user=user, message=txt)

    @staticmethod
    def _save_assistant_response(msg: UserMessage, resp: str) -> None:
        msg.response = resp
        msg.save(update_fields=["response"])

    @staticmethod
    def _save_turn(user_id: int, message: str, response: str, thread: ChatThread) -> Optional[UserMessage]:
        """Save the user message and assistant response to the database for an authenticated user's turn."""
        if not thread:
             logger.error(f"Cannot save turn for user {user_id}: ChatThread object is missing.")
             return None
        try:
            # Create user message with response. User is implicitly linked via the thread.
            user_msg = UserMessage.objects.create(thread=thread, user_id=user_id, message=message, response=response)
            return user_msg
        except Exception as e:
            logger.error(f"Error saving conversation turn to UserMessage for thread {thread.id}: {str(e)}")
            traceback.print_exc()
            return None

    # ── util
    @staticmethod
    def _extract(response) -> str:
        """
        Extract text content from an OpenAI response, handling different response formats.
        
        This method is flexible and will extract text from various OpenAI response structures,
        including direct output_text, message contents, and text delta events.
        """
        # Most common case with simple output_text attribute
        if hasattr(response, "output_text"):
            formatted_text = response.output_text
        else:
            # Fall back to iterating through output items
            text = ""
            for item in getattr(response, "output", []):
                # Handle message type items
                if getattr(item, "type", None) == "message":
                    for c in getattr(item, "content", []):
                        if getattr(c, "type", None) == "output_text":
                            text += getattr(c, "text", "")
                # Handle direct text items
                elif getattr(item, "type", None) == "text":
                    text += getattr(item, "text", "")
            formatted_text = text

        # ------------------------------------------------------------------
        # PHASE 1: PROPER UNICODE NORMALIZATION AT SOURCE
        # This prevents hex corruption from occurring in the first place
        # ------------------------------------------------------------------
        import unicodedata
        import re
        
        try:
            # Ensure proper UTF-8 encoding/decoding to prevent hex corruption
            formatted_text = formatted_text.encode('utf-8', errors='replace').decode('utf-8')
            # Normalize Unicode characters (NFC = canonical composition)
            formatted_text = unicodedata.normalize('NFC', formatted_text)
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            # Fallback: just normalize what we can if encoding fails
            formatted_text = unicodedata.normalize('NFC', formatted_text)
            logger.warning(f"Unicode encoding issue in _extract: {e}")

        # Strip non‑printable / control characters that sometimes creep in
        formatted_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", formatted_text)

        # ------------------------------------------------------------------
        # PHASE 3: MINIMAL SAFETY NET FOR EXTREME EDGE CASES
        # Only keep the most critical patterns as backup
        # ------------------------------------------------------------------
        critical_patterns = [
            (r'(\d{3})b0C\b', r'\1°C'),     # Only 220b0C -> 220°C (very specific)
            (r'(\d{3})f\b', r'\1°F'),       # Only 425f -> 425°F (3 digits only)
        ]
        for pattern, replacement in critical_patterns:
            formatted_text = re.sub(pattern, replacement, formatted_text)

        # Remove any leading "Subject: ..." line the LLM might prepend
        formatted_text = re.sub(r"^Subject:[^\n\r]*[\n\r]+", "", formatted_text, flags=re.IGNORECASE)

        formatted_text = formatted_text.strip()
        return formatted_text

    def _fix_function_args(self, function_name: str, args_str: str) -> str:
        """Ensure that user_id and guest_id are correctly set in function arguments."""
        try:
            args = json.loads(args_str)
            try:
                if function_name in ("modify_meal_plan", "replace_meal_plan_meal"):
                    print(f"FIX_ARGS before func={function_name} args={args}", flush=True)
            except Exception:
                pass
            
            # If the function has a user_id parameter and it's not the current user
            if "user_id" in args:
                if args["user_id"] != self.user_id:
                    args["user_id"] = self.user_id
                    return json.dumps(args)
            
            # Fix guest_id for onboarding tools (common issue where AI confuses username with guest_id)
            onboarding_funcs = ['onboarding_save_progress', 'onboarding_request_password', 'guest_register_user']
            if function_name in onboarding_funcs and "guest_id" in args:
                if args["guest_id"] != self.user_id:
                    args["guest_id"] = self.user_id
                    return json.dumps(args)
            
            # Special case for chef-meal related functions
            chef_meal_funcs = ['replace_meal_plan_meal', 'place_chef_meal_event_order', 'generate_payment_link']
            if function_name in chef_meal_funcs:
                logger.info(f"DEBUG: Special processing for chef meal function: {function_name}")
                logger.info(f"DEBUG: Args before: {args}")
                
                # Add logging for specific functions
                if function_name == 'replace_meal_plan_meal':
                    logger.info(f"DEBUG: replace_meal_plan_meal args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  meal_plan_meal_id: {args.get('meal_plan_meal_id')}")
                    logger.info(f"  chef_meal_id: {args.get('chef_meal_id')}")
                    logger.info(f"  event_id: {args.get('event_id')}")
                    
                elif function_name == 'generate_payment_link':
                    logger.info(f"DEBUG: generate_payment_link args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  order_id: {args.get('order_id')}")
                    
                elif function_name == 'place_chef_meal_event_order':
                    logger.info(f"DEBUG: place_chef_meal_event_order args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  meal_event_id: {args.get('meal_event_id')}")
                    logger.info(f"  quantity: {args.get('quantity')}")
                    logger.info(f"  special_instructions: {args.get('special_instructions')}")
            
            try:
                if function_name in ("modify_meal_plan", "replace_meal_plan_meal"):
                    print(f"FIX_ARGS after func={function_name} args={args}", flush=True)
            except Exception:
                pass
            return args_str
        except Exception as e:
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'fix_function_args',
                'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            return args_str

    def _current_admin_blurb(self, user) -> Optional[str]:
        """
        Return the announcement for this user's locale, if any.
        Includes both global and region-specific announcements.
        """
        today = timezone.localdate()
        iso_week = today.isocalendar()  # (year, week, weekday)
        week_start = date.fromisocalendar(iso_week[0], iso_week[1], 1)  # Monday
        
        # Figure out user's country (via Address model)
        try:
            country_code = user.address.country.code if hasattr(user, 'address') and user.address and user.address.country else ""
        except AttributeError:
            country_code = ""
        
        # Check cache first
        cache_key = f"blurb:{week_start}:{country_code or 'GLOBAL'}"
        cached = get(cache_key)
        if cached is not None:  # Empty string means "none this week"
            return cached or None
        
        # Get global announcement
        global_qs = WeeklyAnnouncement.objects.filter(
            week_start=week_start,
            country__isnull=True
        )
        global_blurb = global_qs.first().content.strip() if global_qs.exists() else ""
        
        # Get country-specific announcement if applicable
        regional_blurb = ""
        if country_code:
            regional_qs = WeeklyAnnouncement.objects.filter(
                week_start=week_start,
                country=country_code
            )
            if regional_qs.exists():
                regional_blurb = regional_qs.first().content.strip()
        
        # Combine the announcements
        combined_blurb = ""
        if regional_blurb and global_blurb:
            # Both regional and global announcements exist, combine them
            combined_blurb = f"{regional_blurb}\n\n*******\n\n{global_blurb}"
        elif regional_blurb:
            # Only regional announcement exists
            combined_blurb = regional_blurb
        elif global_blurb:
            # Only global announcement exists
            combined_blurb = global_blurb
        
        # Cache for an hour
        set(cache_key, combined_blurb, 60 * 60)
        return combined_blurb or None

    def _validate_and_clean_history(self, history: list) -> list:
        """
        • Keep all plain user/assistant messages.
        • Keep function_call ⇄ function_call_output pairs.
        • If a call lacks an output, keep it ONE extra turn; then drop it.
        """
        cleaned = []
        pending_next: Dict[str, Dict[str, Any]] = {}

        for item in history:
            role = item.get("role")
            if role in ("user", "assistant"):
                cleaned.append(item)
                continue

            if item.get("type") == "function_call":
                cid = item.get("id")
                has_output = any(
                    o.get("type") == "function_call_output"
                    and o.get("call_id") == cid
                    for o in history
                )
                if has_output:
                    cleaned.append(item)
                else:
                    # keep for exactly one turn before discarding
                    if cid not in self._pending_calls:
                        pending_next[cid] = item
                    cleaned.append(item)
                continue

            if item.get("type") == "function_call_output":
                cleaned.append(item)
                continue

        # remember which calls we already waited on
        self._pending_calls = pending_next
        return cleaned

    def _add_previous_context(self, prev_id: Optional[str], history: List[Dict[str, Any]]) -> None:
        """Add context (function calls/outputs) from cache using the previous response ID."""
        if not prev_id:
            return
            

        if prev_id in self.function_calls_cache:
            cached_turn_data = self.function_calls_cache[prev_id]
            
            # Track which call IDs are already in history (e.g., if manually added)
            call_ids_in_history = set()
            for item in history:
                if item.get('type') == 'function_call' and 'call_id' in item:
                    call_ids_in_history.add(item['call_id'])
                if item.get('type') == 'function_call_output' and 'call_id' in item:
                    call_ids_in_history.add(item['call_id'])
            
            # Add calls and outputs from the cache, ensuring pairs
            added_calls = 0
            # Sort by call_id just for deterministic order if needed
            sorted_call_ids = sorted(cached_turn_data.keys())
            
            for call_id in sorted_call_ids:
                call_data = cached_turn_data[call_id]
                # Only add if both call and output exist and aren't already in history
                if call_data.get("call") and call_data.get("output") and call_id not in call_ids_in_history:
                    history.append(call_data["call"])
                    history.append(call_data["output"])
                    added_calls += 1

    # ─────────────────────────────────────────  user summary streaming
    def stream_user_summary(self, summary_date=None) -> Generator[Dict[str, Any], None, None]:
        """
        Stream the generation of a user daily summary.
        
        Creates or fetches a UserDailySummary record and streams its generation process.
        Returns a generator yielding status events as the summary is generated.
        
        Args:
            summary_date: Optional date for the summary (default: today in user's timezone)
            
        Returns:
            Generator yielding event dictionaries with progress and result information
        """
        from customer_dashboard.models import UserDailySummary
        import uuid
        
        if self._is_guest(self.user_id):
            yield {"type": "error", "message": "User summaries are only available for authenticated users"}
            return
            
        try:
            user = CustomUser.objects.get(id=self.user_id)
            
            # Generate a unique ticket for tracking this summary request
            ticket = f"sum_{uuid.uuid4().hex[:8]}"
            
            # Set summary_date to today in user's timezone if not provided
            if summary_date is None:
                user_timezone = ZoneInfo(user.timezone if user.timezone else 'UTC')
                summary_date = timezone.now().astimezone(user_timezone).date()
            elif isinstance(summary_date, str):
                # If it's a string, parse it as a date
                summary_date = datetime.strptime(summary_date, '%Y-%m-%d').date()
                
            # Emit initial status
            yield {"type": "status", "status": "starting", "ticket": ticket}
            
            # Check for existing summary
            summary = UserDailySummary.objects.filter(
                user=user,
                summary_date=summary_date,
                status=UserDailySummary.COMPLETED
            ).first()
            
            if summary:
                # Return existing summary immediately
                yield {"type": "status", "status": "completed", "ticket": ticket}
                yield {"type": "summary", 
                       "summary": summary.summary,
                       "summary_date": summary.summary_date.strftime('%Y-%m-%d'),
                       "created_at": summary.created_at.isoformat() if summary.created_at else None,
                       "updated_at": summary.updated_at.isoformat() if summary.updated_at else None
                }
                return
                
            # No completed summary exists - create or update a pending one
            summary, created = UserDailySummary.objects.get_or_create(
                user=user,
                summary_date=summary_date,
                defaults={'status': UserDailySummary.PENDING, 'ticket': ticket}
            )
            
            if not created and summary.status != UserDailySummary.COMPLETED:
                # Update existing non-completed summary
                summary.status = UserDailySummary.PENDING
                summary.ticket = ticket
                summary.save(update_fields=["status", "ticket"])
            
            # Start generating the summary in background
            from meals.email_service import generate_user_summary
            generate_user_summary.delay(user.id, summary_date.strftime('%Y-%m-%d'))
            
            # Inform frontend that generation has started
            yield {"type": "status", "status": "pending", "ticket": ticket}
            
            # Poll for updates until the summary is complete or fails
            max_attempts = 12  # 30 seconds total (12 * 2.5s)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(2.5)  # Wait 2.5 seconds between checks
                
                # Refresh the summary from the database
                summary.refresh_from_db()
                
                # Check if the summary is completed or has an error
                if summary.status == UserDailySummary.COMPLETED:
                    yield {"type": "status", "status": "completed", "ticket": ticket}
                    yield {"type": "summary", 
                           "summary": summary.summary,
                           "summary_date": summary.summary_date.strftime('%Y-%m-%d'),
                           "created_at": summary.created_at.isoformat() if summary.created_at else None,
                           "updated_at": summary.updated_at.isoformat() if summary.updated_at else None
                    }
                    return
                elif summary.status == UserDailySummary.ERROR:
                    yield {"type": "error", "message": "Error generating summary", "ticket": ticket}
                    return
                
                # Still pending - yield a progress update
                yield {"type": "status", "status": "pending", "ticket": ticket, 
                       "progress": f"{attempt + 1}/{max_attempts}"}
                
                attempt += 1
            
            # If we've exhausted our attempts but the summary is still pending
            yield {"type": "status", "status": "pending", "ticket": ticket, 
                   "message": "Summary generation is taking longer than expected. Please check back later."}
                       
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"stream_user_summary", "traceback": traceback.format_exc()})
            yield {"type": "error", "message": f"An error occurred: {str(e)}"}
            return

    def _local_chef_and_meal_events(self, user: CustomUser) -> str:
        """
        Get information about local chefs and their upcoming meal events for a user.
        Returns a formatted string suitable for inclusion in the prompt.
        """
        try:
            # Get user's postal code from their address
            if not hasattr(user, 'address') or not user.address or not user.address.input_postalcode:
                return "No local chef information available (address not set)."

            postal_code = user.address.input_postalcode

            # Find chefs that serve this postal code
            chef_ids = ChefPostalCode.objects.filter(
                postal_code__code=postal_code
            ).values_list('chef_id', flat=True)

            if not chef_ids:
                return "No chefs currently serve your area."

            # Get upcoming events from these chefs
            now = timezone.now()
            events = ChefMealEvent.objects.filter(
                chef_id__in=chef_ids,
                event_date__gte=now.date(),
                status__in=['scheduled', 'open'],
                order_cutoff_time__gt=now,
                orders_count__lt=F('max_orders')
            ).select_related('chef', 'chef__user', 'meal').order_by('event_date', 'event_time')[:20]  # Limit to 20 upcoming events

            if not events:
                return "No upcoming meal events from local chefs at this time."

            # Format the information
            event_info = []
            for event in events:
                event_info.append(
                    f"• {event.meal.name} by Chef {event.chef.user.username} "
                    f"on {event.event_date.strftime('%A, %B %d')} at {event.event_time.strftime('%I:%M %p')} "
                    f"(${float(event.current_price):.2f}/serving)"
                )

            return (
                "LOCAL CHEF UPDATES\n"
                f"You have {len(chef_ids)} local chef{'s' if len(chef_ids) > 1 else ''} in your area. "
                "Here are some upcoming meals:\n"
                f"{chr(10).join(event_info)}"
            )

        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_local_chef_and_meal_events", "traceback": traceback.format_exc()})
            return "Unable to retrieve local chef information at this time."

    def _get_user_chat_summary(self, user: CustomUser) -> str:
        """
        Retrieve the consolidated chat summary for a user if available
        """
        try:
            user_summary = UserChatSummary.objects.filter(
                user=user,
                status=UserChatSummary.COMPLETED
            ).first()
            
            if user_summary and user_summary.summary:
                return f"USER CHAT HISTORY SUMMARY\n{user_summary.summary}\n\n"
            
            return ""
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_get_user_chat_summary", "traceback": traceback.format_exc()})
            return ""

    # ────────────────────────────────────────────────────────────────────
    #  Internal Helper for Formatting Email Content
    # ────────────────────────────────────────────────────────────────────
    def _format_text_for_email_body(self, raw_text: str) -> str:
        """
        Transform plain text into Django template-compatible HTML sections.
        Returns the main content section for backward compatibility.
        Use _get_django_template_sections() for full template integration.
        
        Args:
            raw_text: The raw text content to format
            
        Returns:
            Formatted HTML string for email_body_main (backward compatible)
        """
        return self._django_email_formatter.format_text_for_email_body(raw_text)
    
    def _get_django_template_sections(self, raw_text: str, intent_context: Optional[Dict] = None) -> DjangoEmailBody:
        """
        Get all Django template sections for complete integration.
        
        Args:
            raw_text: The raw text content to format
            intent_context: Optional intent analysis context for better formatting
            
        Returns:
            DjangoEmailBody with email_body_main, email_body_data, and email_body_final
        """
        return self._django_email_formatter.get_django_template_sections(raw_text, intent_context)

    # ────────────────────────────────────────────────────────────────────
    #  Email Processing Method
    # ────────────────────────────────────────────────────────────────────
    def generate_email_response(self, message_content: str) -> Dict[str, Any]:
        """
        Processes a message for email reply, handling iterative tool calls
        until a final textual response is obtained from the assistant.

        This method is designed for authenticated users and asynchronous processing
        (e.g., via Celery tasks for email replies). It manages conversation
        history and state persistence.

        Args:
            message_content (str): The aggregated message content from the user's email(s).

        Returns:
            Dict[str, Any]: A dictionary containing:
                - "status" (str): "success" or "error".
                - "message" (str): The final textual response from the assistant.
                                   Can be an empty string if the assistant provides
                                   no text or a fallback error message.
                - "response_id" (str, optional): The ID of the *final* OpenAI
                                                 response in the conversational turn.
        """
        # 3.1. Initial Setup & Pre-checks
        # User Authentication Check
        if self._is_guest(self.user_id):
            logger.error(f"generate_email_response called for a guest user ID: {self.user_id}. This is not supported.")
            return {"status": "error", "message": "Email processing is for authenticated users only.", "response_id": None}
            
        # Model Selection
        model = choose_model(
            user_id=self.user_id,
            is_guest=False, 
            question=message_content
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_AUTH_FALLBACK
            
        # History Initialization
        chat_thread = self._get_or_create_thread(self.user_id)
        current_history = chat_thread.openai_input_history.copy() if chat_thread.openai_input_history else []
        if not current_history:
            current_history.append({"role": "system", "content": self.system_message})
        current_history.append({"role": "user", "content": message_content})
        
        # Truncate history if it's getting too long to prevent context length exceeded errors
        current_history = self._truncate_history_if_needed(current_history, max_messages=30, max_tokens=25000)
            
        # State Variables
        final_output_text = ""
        final_response_id = None
        prev_resp_id_for_api = None
        max_tool_iterations = 5
        iterations = 0
        # Initialize tool_calls_in_response before the loop
        tool_calls_in_response = []
        user = CustomUser.objects.get(id=self.user_id)

        # 3.2. Main Processing Loop (Iterative Tool Calling)
        try:
            while iterations < max_tool_iterations:
                iterations += 1
                

                
                # Validate and clean history before sending to OpenAI
                current_history = self._validate_and_clean_history(current_history)
                
                # Debug: Log history structure before API call
                if logger.isEnabledFor(logging.DEBUG):
                    call_ids = set()
                    output_ids = set()
                    for item in current_history:
                        if item.get('type') == 'function_call' and 'call_id' in item:
                            call_ids.add(item['call_id'])
                        elif item.get('type') == 'function_call_output' and 'call_id' in item:
                            output_ids.add(item['call_id'])
                
                # OpenAI API Call - Standard call for all iterations
                try:
                    resp = self.client.responses.create(
                        model=model,
                        input=current_history,
                        instructions=self._instructions(is_guest=False),
                        tools=self._get_tools_for_user(False),
                        parallel_tool_calls=True,
                        previous_response_id=prev_resp_id_for_api,
                    )
                except Exception as api_error:
                    # Handle context length exceeded errors specifically
                    if "context_length_exceeded" in str(api_error).lower() or "context window" in str(api_error).lower():
                        logger.warning(f"Context length exceeded for user {self.user_id}. Attempting with more aggressive truncation.")
                        # More aggressive truncation and retry
                        current_history = self._truncate_history_if_needed(current_history, max_messages=20, max_tokens=16000)
                        # Validate and clean history after truncation
                        current_history = self._validate_and_clean_history(current_history)
                        try:
                            resp = self.client.responses.create(
                                model=model,
                                input=current_history,
                                instructions=self._instructions(is_guest=False),
                                tools=self._get_tools_for_user(False),
                                parallel_tool_calls=True,
                                previous_response_id=None,  # Don't use previous response ID on retry
                            )
                        except Exception as retry_error:
                            # n8n traceback
                            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                            requests.post(n8n_traceback_url, json={"error": str(retry_error), "source":"generate_email_response", "traceback": traceback.format_exc()})
                            raise retry_error
                    else:
                        # Re-raise if it's not a context length error
                        raise api_error
                
                final_response_id = resp.id
                prev_resp_id_for_api = final_response_id
                
                # Extract Tool Calls
                tool_calls_in_response = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
                
                # Condition: No Tool Calls in Response (End of Turn)
                if not tool_calls_in_response:
                    # Extract the response text directly
                    try:
                        final_output_text = self._extract(resp)
                    except Exception as extract_error:
                        logger.error(f"generate_email_response: Error extracting text: {extract_error}")
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
                        requests.post(n8n_traceback_url, json={"error": str(extract_error), "source":"generate_email_response", "traceback": traceback.format_exc()})
                        final_output_text = "I'm sorry, but I encountered an issue processing your message. Please try again or contact support."
                    
                    if final_output_text:
                        current_history.append({"role": "assistant", "content": final_output_text})
                    logger.info(f"generate_email_response: No tool calls. Extracted text: '{final_output_text[:100]}...' for user {self.user_id}")
                    break
                    
                # Condition: Tool Calls Present
                logger.info(f"generate_email_response: Found {len(tool_calls_in_response)} tool call(s) for user {self.user_id}.")
                
                for tool_call_item in tool_calls_in_response:
                    # Append function_call to history
                    call_entry = {
                        "type": "function_call",
                        "name": tool_call_item.name,
                        "arguments": tool_call_item.arguments,
                        "call_id": tool_call_item.call_id
                    }
                    current_history.append(call_entry)
                    
                    # Execute Tool
                    args_json_str = tool_call_item.arguments
                    fixed_args_json_str = self._fix_function_args(tool_call_item.name, args_json_str)
                    
                    tool_result_data = None
                    try:
                        logger.info(f"generate_email_response: Executing tool {tool_call_item.name} with args: {fixed_args_json_str} for user {self.user_id}")
                        
                        # Time the tool execution
                        email_tool_start_time = time.time()
                        mock_call_object = type("Call", (), {
                            "call_id": tool_call_item.call_id,
                            "function": type("F", (), {
                                "name": tool_call_item.name,
                                "arguments": fixed_args_json_str
                            })
                        })
                        tool_result_data = handle_tool_call(mock_call_object)
                        email_tool_execution_time = time.time() - email_tool_start_time
                        
                        logger.info(f"generate_email_response: Tool {tool_call_item.name} result: {str(tool_result_data)[:200]}... for user {self.user_id}")
                            
                    except Exception as e_tool:
                        logger.error(f"generate_email_response: Error executing tool {tool_call_item.name} for user {self.user_id}: {e_tool}", exc_info=True)
                        #n8n traceback
                        n8n_traceback = {
                            'error': str(e_tool),
                            'source': 'tool_call',
                            'traceback': traceback.format_exc()
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                        tool_result_data = {"status": "error", "message": f"Error executing tool {tool_call_item.name}: {str(e_tool)}"}
                        
                    # Append function_call_output to history
                    output_entry = {
                        "type": "function_call_output",
                        "call_id": tool_call_item.call_id,
                        "output": json.dumps(tool_result_data)
                    }
                    current_history.append(output_entry)
                
                # Max Iterations Check
                if iterations >= max_tool_iterations and tool_calls_in_response:
                    logger.warning(f"generate_email_response: Reached max tool iterations ({max_tool_iterations}) for user {self.user_id}. API may still want to call tools.")
                    final_output_text = "I'm encountering some complexity with your request. Could you please try again, perhaps simplifying it, or use the web interface for a more detailed interaction?"
                    current_history.append({"role": "assistant", "content": final_output_text})
                    break
            
            # 3.3. Post-Loop Processing & Persistence
            logger.info(f"generate_email_response: Loop finished for user {self.user_id}. Final text: '{final_output_text[:100]}...'")
            
            # No text cleanup needed - allow natural assistant responses
            
            # Persist State
            if final_response_id:
                self._persist_state(self.user_id, final_response_id, is_guest=False, history=current_history)
                if chat_thread and message_content and final_output_text:
                    self._save_turn(self.user_id, message_content, final_output_text, chat_thread)
            else:
                logger.warning(f"generate_email_response: No final_response_id was captured for user {self.user_id}. State may not be fully persisted.")
                
            # Return Success
            return {"status": "success", "message": final_output_text, "response_id": final_response_id}
            
        # 3.4. Outer Error Handling
        except Exception as e_outer:
            logger.error(f"generate_email_response: Unhandled error for user {self.user_id}: {e_outer}", exc_info=True)
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e_outer), "source":"generate_email_response", "traceback": traceback.format_exc()})
            return {
                "status": "error", 
                "message": f"An unexpected error occurred during email processing: {str(e_outer)}", 
                "response_id": final_response_id
            }

    def process_and_reply_to_email(
        self, 
        message_content: str, 
        recipient_email: str, 
        user_email_token: str, 
        original_subject: str, 
        in_reply_to_header: Optional[str], 
        email_thread_id: Optional[str],
        openai_thread_context_id_initial: Optional[str] = None,
        template_key: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Processes an aggregated email message, gets a response from the assistant,
        and then triggers n8n to send the reply email.
        This is a non-streaming method.
        Assumes self.user_id is already set correctly for an authenticated user.
        """
        # Ensure DB connection is fresh for long-running worker processes
        try:
            close_old_connections()
        except Exception:
            pass
        if self._is_guest(self.user_id):
            logger.error(f"process_and_reply_to_email called for a guest user ID: {self.user_id}. This should not happen.")
            return {"status": "error", "message": "Email processing is only for authenticated users."}

        logger.info(f"MealPlanningAssistant: Processing email for user {self.user_id}, to_recipient: {recipient_email}")

        # Get the current active thread for this user
        chat_thread = self._get_or_create_thread(self.user_id)
        
        # Strip email headers from the message content
        cleaned_message_content = self._strip_email_headers(message_content)
        
        # 1. Get the assistant's response using generate_email_response logic
        # This handles history, model selection, tool calls, iterations, and persistence.
        assistant_response_data = self.generate_email_response(message_content=cleaned_message_content)
        if assistant_response_data.get("status") == "error":
            logger.error(f"MealPlanningAssistant: Error getting response from generate_email_response for user {self.user_id}: {assistant_response_data.get('message')}")
            # Still attempt to send a generic error reply via email
            raw_reply_content = "I encountered an issue processing your request. Please try again later or contact support if the problem persists."
            new_openai_response_id = None
        else:
            raw_reply_content = assistant_response_data.get('message', 'Could not process your request at this time. Please try again later via the web interface.')
            new_openai_response_id = assistant_response_data.get('response_id', None)
            logger.info(f"MealPlanningAssistant: Received response for user {self.user_id}. OpenAI response ID: {new_openai_response_id}")

        # 2. Get structured sections. If a template_key is provided, attempt JSON-schema output.
        structured_sections = None
        if template_key and template_key != 'emergency_supply':
            try:
                # Ask model to return structured JSON for the template_key
                # Build a minimal, explicit instruction for structured output
                from customer_dashboard.template_router import get_schema_for_key
                schema_model = get_schema_for_key(template_key)
                raw_schema = schema_model.model_json_schema()
                schema_dict = self._clean_schema_for_openai(raw_schema)

                # Make a second, lightweight call to shape the final output
                shaping_prompt = [
                    {"role": "system", "content": "You will transform the assistant's prior reply into structured JSON."},
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY JSON matching this schema. Do not include explanations.\n"
                            f"Schema: {schema_dict}\n"
                            "Use these inputs to populate fields: \n"
                            f"RAW_REPLY: {raw_reply_content}"
                        ),
                    },
                ]

                resp = self.client.responses.create(
                    model=MODEL_AUTH_FALLBACK,
                    input=shaping_prompt,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "email_structured",
                            "schema": schema_dict,
                            "strict": True,
                        }
                    },
                )
                import json as _json
                structured_payload = _json.loads(resp.output_text)
                structured_sections = structured_payload
            except Exception as _shape_err:
                logger.error(f"Email structured shaping failed for key '{template_key}': {_shape_err}")
        elif template_key == 'emergency_supply':
            # For emergency_supply, rely only on the Pydantic-validated context passed in (emergency_list)
            logger.info("Skipping router-based JSON shaping for 'emergency_supply'; using Pydantic-derived context.")

        # Fallback: derive sections via formatter
        if not structured_sections:
            django_email_body = self._get_django_template_sections(raw_reply_content)
            base_sections = {
                'main': django_email_body.email_body_main,
                'data': django_email_body.email_body_data,
                'final': django_email_body.email_body_final,
            }
        else:
            # Map structured payload into base HTML sections; let partials handle rich rendering
            # We support both generic and intent-specific payloads
            main_html = structured_sections.get('main_html') or structured_sections.get('main_text') or ''
            data_html = ''  # data may be rendered from structured fields in partials
            final_html = structured_sections.get('final_html') or structured_sections.get('final_text') or ''
            base_sections = {
                'main': main_html,
                'data': data_html,
                'final': final_html,
            }

        # 3. Render the full email using the Django template with structured sections
        try:
            # Fetch user for their name, retry once if the DB connection is stale
            try:
                user = CustomUser.objects.get(id=self.user_id)
            except (OperationalError, InterfaceError):
                logger.warning("DB connection issue when fetching user; refreshing connections and retrying once")
                close_old_connections()
                user = CustomUser.objects.get(id=self.user_id)
            user_name = user.get_full_name() or user.username
            
            # Check if the user has unsubscribed from emails
            if getattr(user, 'unsubscribed_from_emails', False):
                logger.info(f"MealPlanningAssistant: User {self.user_id} has unsubscribed from emails. Skipping email reply.")
                return {"status": "skipped", "message": "User has unsubscribed from emails."}
                
            # Get user's preferred language for translation
            user_preferred_language = _get_language_name(getattr(user, 'preferred_language', 'en'))
        except CustomUser.DoesNotExist:
            user_name = "there" # Fallback name
            user_preferred_language = 'en'  # Default to English if user not found
            logger.warning(f"User {self.user_id} not found when preparing email, using fallback name.")
        
        site_domain = os.getenv('STREAMLIT_URL')
        profile_url = f"{site_domain}/profile" # Adjust if your profile URL is different

        # 3.5. Route sections through a template router if a template_key was provided
        css_classes_extra: List[str] = []
        try:
            if template_key:
                from customer_dashboard.template_router import render_email_sections
                # Merge caller-provided context with structured fields (if any)
                merged_context = {}
                if template_context and isinstance(template_context, dict):
                    merged_context.update(template_context)
                try:
                    if structured_sections and isinstance(structured_sections, dict):
                        # Do NOT override explicit template_context keys with model-shaped fields
                        for _k, _v in structured_sections.items():
                            if _k not in merged_context:
                                merged_context[_k] = _v
                        # Normalize known fields for safety (handle common LLM shape drift)
                        try:
                            import re as _re
                            if 'key_highlights' in merged_context:
                                kh = merged_context['key_highlights']
                                if isinstance(kh, str):
                                    parts = [_p.strip(" -•\t\r") for _p in _re.split(r"[\n\r•]+", kh) if _p and _p.strip(" -•")]
                                    merged_context['key_highlights'] = parts[:5]
                                elif isinstance(kh, list):
                                    merged_context['key_highlights'] = [str(x).strip() for x in kh if str(x).strip()][:5]
                        except Exception:
                            pass
                except Exception:
                    pass
                rendered_sections, css_classes_extra = render_email_sections(
                    template_key=template_key,
                    section_html=base_sections,
                    extra_context=merged_context,
                )
                email_body_main = rendered_sections['main']
                email_body_data = rendered_sections['data']
                email_body_final = rendered_sections['final']
            else:
                email_body_main = base_sections['main']
                email_body_data = base_sections['data']
                email_body_final = base_sections['final']
        except Exception as _route_err:
            logger.error(f"Template routing failed; using raw sections. Error: {_route_err}")
            email_body_main = base_sections['main']
            email_body_data = base_sections['data']
            email_body_final = base_sections['final']

        email_html_content = render_to_string(
            'customer_dashboard/assistant_email_template.html',
            {
                'user_name': user_name,
                'email_body_main': email_body_main,
                'email_body_data': email_body_data,
                'email_body_final': email_body_final,
                'profile_url': profile_url,
                'personal_assistant_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') else None,
                'css_classes': css_classes_extra,
            }
        )
        
        # Translate the email content if needed
        if user_preferred_language != 'en':
            try:
                email_html_content = translate_paragraphs(
                    email_html_content,
                    user_preferred_language
                )
                logger.info(f"Successfully translated email content to {_get_language_name(user_preferred_language)} ({user_preferred_language}) for user {self.user_id}")
            except Exception as e:
                logger.error(f"Error translating email content for user {self.user_id} to {_get_language_name(user_preferred_language)} ({user_preferred_language}): {e}")
                # Continue with the original English content as fallback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"translate_email_content", "traceback": traceback.format_exc()})
            

        # 4. Trigger n8n to send this reply_content back to recipient_email
        n8n_webhook_url = os.getenv('N8N_EMAIL_REPLY_WEBHOOK_URL')
        if not n8n_webhook_url:
            logger.error(f"MealPlanningAssistant: N8N_EMAIL_REPLY_WEBHOOK_URL not configured. Cannot send email reply for user {self.user_id}.")
            # Log the intended reply locally if n8n is not configured
            logger.info(f"Intended email reply for {recipient_email} (User ID: {self.user_id}):\nSubject: Re: {original_subject}\nBody:\n{email_html_content}")
            return {"status": "error", "message": "N8N_EMAIL_REPLY_WEBHOOK_URL not configured."}

        # Ensure original_subject has content
        if not original_subject or original_subject.strip() == "":
            logger.warning(f"Empty subject received for user {self.user_id}. Using default subject.")
            original_subject = "Message from your sautai Assistant"
        
        # Handle reply prefix
        subject_prefix = "Re: "
        if original_subject.lower().startswith("re:") or original_subject.lower().startswith("aw:"):
            subject_prefix = ""
        final_subject = f"{subject_prefix}{original_subject}"

        payload = {
            'status': 'success', 
            'action': 'send_reply', 
            'reply_content': email_html_content, # Send the fully rendered HTML
            'recipient_email': recipient_email,
            'from_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user_email_token}@sautai.com", 
            'original_subject': final_subject,
            'in_reply_to_header': in_reply_to_header,
            'email_thread_id': email_thread_id,
            'openai_response_id': new_openai_response_id,
            'chat_thread_id': chat_thread.id if chat_thread else None
        }

        try:
            # if settings.DEBUG:
            #     logger.info(f"MealPlanningAssistant: Skipping n8n webhook for user {self.user_id} in DEBUG mode.")
            #     logger.info(f"MealPlanningAssistant: Payload: {json.dumps(payload)}")
            #     return {"status": "success", "message": "Email reply successfully sent to n8n.", "n8n_response_status": "skipped"}
            # else:
            logger.info(f"MealPlanningAssistant: Posting to n8n webhook for user {self.user_id}. URL: {n8n_webhook_url}")
            response = requests.post(n8n_webhook_url, json=payload, timeout=15)
            response.raise_for_status() 
            logger.info(f"MealPlanningAssistant: Successfully posted assistant reply to n8n for user {self.user_id}. Status: {response.status_code}")
            return {"status": "success", "message": "Email reply successfully sent to n8n.", "n8n_response_status": response.status_code}
        except requests.RequestException as e:
            logger.error(f"MealPlanningAssistant: Failed to post assistant reply to n8n for user {self.user_id}: {e}. Payload: {json.dumps(payload)}")
            # Log the intended reply if n8n call failed
            logger.info(f"Failed n8n call. Intended email reply for {recipient_email} (User ID: {self.user_id}):\nSubject: {final_subject}\nBody:\n{email_html_content}")
            return {"status": "error", "message": f"Failed to send email via n8n: {str(e)}"}
        except Exception as e_general: # Catch any other unexpected errors during payload prep or call
            logger.error(f"MealPlanningAssistant: Unexpected error during n8n email sending for user {self.user_id}: {e_general}. Payload: {json.dumps(payload if 'payload' in locals() else 'Payload not generated')}", exc_info=True)
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e_general), "source":"process_and_reply_to_email", "traceback": traceback.format_exc()})
            return {"status": "error", "message": f"Unexpected error during email sending preparation: {str(e_general)}"}

    @classmethod
    def send_notification_via_assistant(
        cls, 
        user_id: int, 
        message_content: str, 
        subject: str = None,
        template_key: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Static utility method that wraps process_and_reply_to_email to allow tasks to
        send emails through the assistant.
        
        This method is designed to be called from Celery tasks to route notifications 
        through the assistant rather than sending them directly.
        
        Args:
            user_id: The ID of the user to notify
            message_content: The message content to send
            subject: Optional subject line (defaults to "Update from your meal assistant")
            
        Returns:
            Dict with status and result information
        """
        try:
            # In CI tests, avoid side effects unless explicitly allowed
            if getattr(settings, "TEST_MODE", False):
                running_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules or any(arg == "test" or "pytest" in arg for arg in sys.argv)
                allow_emails = os.getenv("ALLOW_ASSISTANT_EMAILS", "").lower() in ("1", "true", "yes", "on")
                if running_pytest and not allow_emails:
                    return {"status": "skipped", "reason": "test_mode"}

            # Ensure DB connection is usable; be resilient in tests/workers
            user = None
            for attempt in range(3):
                try:
                    # Refresh or reopen a stale/closed connection
                    try:
                        close_old_connections()
                        connection.ensure_connection()
                    except Exception:
                        # Best‑effort: if ensure_connection isn't available or fails, continue to query
                        pass

                    user = (
                        CustomUser.objects
                        .only("id", "email", "email_confirmed", "unsubscribed_from_emails", "email_token")
                        .get(id=user_id)
                    )
                    break
                except (OperationalError, InterfaceError, DatabaseError) as db_err:
                    logger.warning(
                        f"send_notification_via_assistant: DB fetch attempt {attempt+1} failed for user {user_id}: {db_err}"
                    )
                    # brief backoff then retry
                    time.sleep(0.05)
                    continue
            if user is None:
                logger.error(
                    f"send_notification_via_assistant: skipping notification; database unavailable for user {user_id}"
                )
                return {"status": "skipped", "reason": "db_unavailable"}
            
            # Skip if email not confirmed
            if not user.email_confirmed:
                logger.warning(f"Skipping notification for user {user_id} with unconfirmed email")
                return {"status": "skipped", "reason": "email_not_confirmed"}
                
            # Skip if user has unsubscribed from emails
            if getattr(user, 'unsubscribed_from_emails', False):
                logger.warning(f"Skipping notification for user {user_id} who has unsubscribed from emails")
                return {"status": "skipped", "reason": "user_unsubscribed"}
                
            # Initialize assistant
            assistant = cls(user_id=user_id)
            
            # Use user's email, fallback to a default
            recipient_email = user.email
            
            # Build the subject line
            if not subject:
                subject = "Update from your meal assistant"
                
            # Call process_and_reply_to_email (most params are None for first-contact emails)
            result = assistant.process_and_reply_to_email(
                message_content=message_content,
                recipient_email=recipient_email,
                user_email_token=str(user.email_token) if hasattr(user, 'email_token') else None,
                original_subject=subject,
                in_reply_to_header=None,
                email_thread_id=None,
                template_key=template_key,
                template_context=template_context,
            )
            
            return result
        except CustomUser.DoesNotExist:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            try:
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={"error": f"User with ID {user_id} not found when sending notification", "source":"send_notification_via_assistant", "traceback": traceback.format_exc()}, timeout=5)
            except Exception:
                pass
            return {"status": "error", "reason": "user_not_found"}
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            try:
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_notification_via_assistant", "traceback": traceback.format_exc()}, timeout=5)
            except Exception:
                pass
            return {"status": "error", "reason": str(e)}

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of tokens for a given text.
        Approximates ~4 characters per token for English text.
        """
        return len(text) // 4
    
    def _truncate_history_if_needed(self, history: List[Dict[str, Any]], max_messages: int = 50, max_tokens: int = 32000) -> List[Dict[str, Any]]:
        """
        Truncate conversation history if it's too long, keeping the system message 
        and the most recent messages. Uses both message count and token estimation.
        Special handling for function calls to maintain call/output pairs.
        
        Args:
            history: The conversation history list
            max_messages: Maximum number of messages to keep (default 50)
            max_tokens: Maximum estimated tokens to keep (default 32000 for most models)
            
        Returns:
            Truncated history list
        """
        if len(history) <= max_messages:
            # Still check token count even if message count is OK
            total_tokens = sum(self._estimate_tokens(str(msg.get("content", ""))) for msg in history)
            if total_tokens <= max_tokens:
                return history
        
        # Group messages to preserve function call pairs
        grouped_items = []
        i = 0
        while i < len(history):
            msg = history[i]
            if msg.get("type") == "function_call" and "call_id" in msg:
                # Look for the matching output
                call_id = msg["call_id"]
                output_found = False
                for j in range(i + 1, len(history)):
                    if (history[j].get("type") == "function_call_output" and 
                        history[j].get("call_id") == call_id):
                        # Group the call and output together
                        grouped_items.append([msg, history[j]])
                        output_found = True
                        # Skip both items in the main loop
                        if j == i + 1:
                            i += 2  # They're consecutive
                        else:
                            # Mark the output as processed
                            history[j] = {"_processed": True}
                            i += 1
                        break
                if not output_found:
                    # Orphaned function call, treat as single item
                    grouped_items.append([msg])
                    i += 1
            elif msg.get("type") == "function_call_output" and not msg.get("_processed"):
                # Orphaned output, treat as single item  
                grouped_items.append([msg])
                i += 1
            elif not msg.get("_processed"):
                # Regular message
                grouped_items.append([msg])
                i += 1
            else:
                i += 1
        
        # Always keep the system message groups (first few items)
        system_groups = []
        non_system_groups = []
        
        for group in grouped_items:
            if any(msg.get("role") == "system" for msg in group):
                system_groups.append(group)
            else:
                non_system_groups.append(group)
        
        # Calculate tokens for system groups
        system_tokens = 0
        for group in system_groups:
            for msg in group:
                system_tokens += self._estimate_tokens(str(msg.get("content", "") or msg.get("output", "") or str(msg)))
        
        # Keep the most recent groups within token and count limits
        available_tokens = max_tokens - system_tokens
        recent_groups = []
        current_tokens = 0
        total_messages = sum(len(group) for group in system_groups)
        
        # Add groups from most recent, checking token count and message count
        for group in reversed(non_system_groups):
            group_tokens = 0
            for msg in group:
                group_tokens += self._estimate_tokens(str(msg.get("content", "") or msg.get("output", "") or str(msg)))
            
            group_message_count = len(group)
            
            if (total_messages + len(recent_groups) * 2 + group_message_count <= max_messages and 
                current_tokens + group_tokens <= available_tokens):
                recent_groups.insert(0, group)  # Insert at beginning to maintain order
                current_tokens += group_tokens
                total_messages += group_message_count
            else:
                break
        
        # Flatten the groups back to a single list
        truncated_history = []
        for group in system_groups + recent_groups:
            truncated_history.extend(group)
        
        if len(history) > len(truncated_history):
            logger.warning(f"Truncated conversation history from {len(history)} to {len(truncated_history)} messages to fit context window (estimated {current_tokens + system_tokens} tokens)")
        
        return truncated_history

    def _strip_email_headers(self, message_content: str) -> str:
        """
        Strip email headers from the message content.
        Handles various header patterns including embedded headers.
        """
        if not message_content:
            return message_content
            
        # Define header patterns to detect and remove
        header_patterns = [
            r'From:\s*[^\n\r]+',
            r'Date:\s*[^\n\r]+', 
            r'Subject:\s*[^\n\r]+',
            r'To:\s*[^\n\r]+',
            r'Message-ID:\s*[^\n\r]+',
            r'In-Reply-To:\s*[^\n\r]+',
            r'References:\s*[^\n\r]+',
            r'Return-Path:\s*[^\n\r]+',
            r'Message from your sautai assistant[^\n\r]*',
            r'Your latest meal plan[^\n\r]*',
            r'-IMAGE REMOVED-[^\n\r]*'
        ]
        
        cleaned_content = message_content
        
        # Remove each header pattern
        for pattern in header_patterns:
            cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and line breaks
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        # If the content is dramatically reduced, it might be mostly headers
        # In that case, try to extract the actual user message
        if len(cleaned_content) < len(message_content) * 0.3:
            # Look for common user message indicators
            user_message_patterns = [
                r'(send that again please|please send|can you|could you|i need|i want)',
                r'(provide|create|make|give me|show me)',
            ]
            
            for pattern in user_message_patterns:
                match = re.search(pattern, message_content, re.IGNORECASE)
                if match:
                    # Extract from the start of the user message
                    start_pos = match.start()
                    potential_message = message_content[start_pos:]
                    
                    # Clean this extracted message
                    for header_pattern in header_patterns:
                        potential_message = re.sub(header_pattern, '', potential_message, flags=re.IGNORECASE)
                    
                    potential_message = re.sub(r'\s+', ' ', potential_message).strip()
                    
                    if len(potential_message) > len(cleaned_content):
                        cleaned_content = potential_message
                    break
        
        # Final fallback - if we removed too much, return the original with basic cleanup
        if len(cleaned_content) < 10 and len(message_content) > 50:
            # Just remove obvious email artifacts but keep the rest
            fallback_content = message_content
            obvious_headers = [
                r'From:\s*[^\s]+@[^\s]+',
                r'Date:\s*\d{2}/\d{2}/\d{4}[^\n\r]*',
                r'Subject:\s*Re:\s*[^\n\r]*'
            ]
            for pattern in obvious_headers:
                fallback_content = re.sub(pattern, '', fallback_content, flags=re.IGNORECASE)
            
            fallback_content = re.sub(r'\s+', ' ', fallback_content).strip()
            if len(fallback_content) > len(cleaned_content):
                cleaned_content = fallback_content
        
        logger.info(f"Header stripping: original length={len(message_content)}, cleaned length={len(cleaned_content)}")
        
        # 🔍 DIAGNOSTIC: Log header stripping details
        logger.info(f"=== HEADER STRIPPING DIAGNOSTIC ===")
        logger.info(f"Original content preview: {repr(message_content[:200])}")
        logger.info(f"Cleaned content preview: {repr(cleaned_content[:200])}")
        if len(cleaned_content) != len(message_content):
            logger.info(f"✅ Headers removed: {len(message_content) - len(cleaned_content)} characters")
        else:
            logger.warning(f"⚠️ No headers detected/removed")
        
        return cleaned_content if cleaned_content else message_content

def generate_guest_id() -> str:
    return f"guest_{uuid.uuid4().hex[:8]}"


class OnboardingAssistant(MealPlanningAssistant):
    """
    Secure onboarding assistant that inherits the proven chat interface from MealPlanningAssistant
    but restricts functionality to onboarding tools and flow only.
    """

    def __init__(self, user_id: Optional[Union[int, str]] = None):
        try:
            # Initialize with the same proven infrastructure as MealPlanningAssistant
            super().__init__(user_id)
            
            # Override system message for onboarding-specific flow
            self.system_message = (
                "You are MJ, sautai's friendly onboarding assistant. "
                "Help users create their account through a simple conversation.\n\n"

                "### PROCESS\n"
                "1. Ask for username\n"
                "2. Ask for email\n"
                "3. Ask for preferred language (e.g., English, Spanish, French, Japanese, etc)\n"
                "4. Ask for dietary preferences (e.g., Vegan, Vegetarian, Gluten-Free, Keto, etc.)\n"
                "5. Ask for allergies (e.g., Peanuts, Tree nuts, Milk, Egg, Wheat, etc.)\n"
                "6. Optionally ask for household members (name, age, dietary preferences)\n"
                "7. When you have username AND email AND language AND dietary preferences AND allergies, call `onboarding_request_password`\n"
                "8. Then ask for password\n\n"

                "### TOOLS\n"
                "• `onboarding_save_progress` – call with individual params (username, email, preferred_language, dietary_preferences, custom_dietary_preferences, allergies, custom_allergies, household_members)\n"
                "• `onboarding_request_password` – call ONLY when you have username AND email AND language AND dietary preferences AND allergies\n\n"

                "### RULES\n"
                "• Be friendly and brief\n"
                "• Save progress after collecting data\n"
                "• Ages should be numbers only (e.g., 3 not \"3 years\")\n"
                "• For dietary preferences, use standard names like 'Vegan', 'Vegetarian', 'Gluten-Free', 'Keto', 'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein', 'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP', 'Diabetic-Friendly', 'Everything'\n"
                "• For allergies, use standard names like 'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', 'Soy', 'Fish', 'Shellfish', 'Sesame', 'None'\n"
                "• If user mentions dietary preferences or allergies not in standard list, use custom_dietary_preferences or custom_allergies arrays\n"
                "• Password will be entered securely in a modal\n"
            )
            
        except Exception as e:
            logger.error(f"OnboardingAssistant.__init__: Error initializing onboarding assistant for user_id={user_id}: {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant.__init__", 
                    "user_id": user_id,
                    "traceback": traceback.format_exc()
                })
            raise

    def _get_tools_for_user(self, is_guest: bool) -> List[Dict[str, Any]]:
        """Override to only allow onboarding tools for security."""
        try:
            # Always use guest tools for onboarding, but filter to onboarding-specific ones only
            from .guest_tools import get_guest_tools
            all_guest_tools = get_guest_tools()
            
            # Security restriction: Only allow onboarding-specific tools
            allowed_tool_names = {
                "guest_register_user", 
                "onboarding_save_progress", 
                "onboarding_request_password"
            }
            
            filtered_tools = [
                tool for tool in all_guest_tools 
                if tool.get("name") in allowed_tool_names
            ]
            
            return filtered_tools
            
        except Exception as e:
            logger.error(f"OnboardingAssistant._get_tools_for_user: Error getting tools for user_id={self.user_id}: {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant._get_tools_for_user", 
                    "user_id": self.user_id,
                    "is_guest": is_guest,
                    "traceback": traceback.format_exc()
                })
            # Return empty list as fallback to prevent complete failure
            return []

    def _instructions(self, is_guest: bool) -> str:
        """Override to provide onboarding-specific instructions with current progress."""
        try:
            base_prompt = self.system_message

            # Append current saved progress to help with context
            try:
                from custom_auth.models import OnboardingSession
                session = OnboardingSession.objects.filter(guest_id=str(self.user_id)).first()
                
                if session and session.data:
                    progress = json.dumps(session.data, indent=2)
                    base_prompt += f"\n### CURRENT SAVED DATA\n```json\n{progress}\n```\n"

                    data = session.data
                    has_username = bool(data.get('username') or data.get('user', {}).get('username'))
                    has_email = bool(data.get('email') or data.get('user', {}).get('email'))
                    has_language = bool(data.get('preferred_language'))
                    has_dietary = bool(data.get('dietary_preferences') or data.get('custom_dietary_preferences'))
                    has_allergies = bool(data.get('allergies') or data.get('custom_allergies'))
                    has_pw = bool(data.get('password') or data.get('user', {}).get('password'))
                    members = data.get('household_members', [])

                    # Determine next question based on what's missing
                    if not has_username:
                        base_prompt += "\nNEXT STEP → Ask for username.\n"
                    elif not has_email:
                        base_prompt += "\nNEXT STEP → Ask for email address.\n"
                    elif not has_language:
                        base_prompt += "\nNEXT STEP → Ask for preferred language (e.g., English, Spanish, French).\n"
                    elif not has_dietary:
                        base_prompt += "\nNEXT STEP → Ask for dietary preferences. If user says 'none' or 'everything', use 'Everything'.\n"
                    elif not has_allergies:
                        base_prompt += "\nNEXT STEP → Ask for allergies. If user says 'none', use 'None'.\n"
                    elif has_username and has_email and has_language and has_dietary and has_allergies and not members:
                        base_prompt += (
                            "\nNEXT STEP → Offer to collect household‑member details "
                            "(name, age, dietary notes). If the user says 'skip', continue.\n"
                        )
                    elif has_username and has_email and has_language and has_dietary and has_allergies and not has_pw:
                        base_prompt += "\nNEXT STEP → Call `onboarding_request_password` and then ask for password.\n"
                    
            except Exception as session_error:
                logger.warning(f"OnboardingAssistant._instructions: Could not load onboarding progress for user_id={self.user_id}: {session_error}", exc_info=True)
                # n8n traceback for session loading errors
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": str(session_error), 
                        "source": "OnboardingAssistant._instructions.session_load", 
                        "user_id": self.user_id,
                        "traceback": traceback.format_exc()
                    })

            return base_prompt
            
        except Exception as e:
            logger.error(f"OnboardingAssistant._instructions: Error building instructions for user_id={self.user_id}: {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant._instructions", 
                    "user_id": self.user_id,
                    "is_guest": is_guest,
                    "traceback": traceback.format_exc()
                })
            # Return basic fallback prompt
            return self.system_message

    def send_message(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Override to check for password prompt structure but use parent's proven send_message logic.
        """
        try:
            # Check if we should expect a password prompt based on the message content
            should_use_password_prompt = self._should_use_password_prompt()
            
            if should_use_password_prompt:
                # Use structured output for password prompts
                is_guest = self._is_guest(self.user_id)
                
                # Get history the same way as parent class
                if is_guest:
                    guest_data = GLOBAL_GUEST_STATE.get(self.user_id, {})
                    if guest_data and "history" in guest_data:
                        history = guest_data["history"].copy()
                        history.append({"role": "user", "content": message})
                    else:
                        history = [
                            {"role": "system", "content": self.system_message},
                            {"role": "user", "content": message},
                        ]
                else:
                    # This shouldn't happen for onboarding, but handle gracefully
                    logger.warning(f"OnboardingAssistant.send_message: Non-guest user in onboarding (unexpected) for user_id={self.user_id}")
                    history = [
                        {"role": "system", "content": self.system_message},
                        {"role": "user", "content": message},
                    ]
                
                try:
                    # Use structured output for password prompts
                    resp = self.client.responses.create(
                        model="gpt-5-mini",
                        input=history,
                        instructions=self._instructions(is_guest),
                        text={
                            "format": {
                                'type': 'json_schema',
                                'name': 'password_prompt',
                                'schema': self._clean_schema_for_openai(PasswordPrompt.model_json_schema())
                            }
                        }
                    )
                    
                    # Parse the structured response
                    password_prompt = _safe_load_and_validate(PasswordPrompt, resp.output_text)
                    response_text = password_prompt.assistant_message
                    
                    # Add to history and persist using parent's method
                    history.append({"role": "assistant", "content": response_text})
                    if is_guest:
                        self._store_guest_state(resp.id, history)
                    
                    return {
                        "status": "success",
                        "message": response_text,
                        "is_password_request": password_prompt.is_password_request,
                        "response_id": resp.id
                    }
                    
                except Exception as structured_error:
                    logger.error(f"OnboardingAssistant.send_message: Error with structured password prompt for user_id={self.user_id}: {structured_error}", exc_info=True)
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    if n8n_traceback_url:
                        requests.post(n8n_traceback_url, json={
                            "error": str(structured_error), 
                            "source": "OnboardingAssistant.send_message.structured_output", 
                            "user_id": self.user_id,
                            "traceback": traceback.format_exc()
                        })
                    # Fall back to regular send_message
            
            # Use parent's proven send_message logic for all other cases
            result = super().send_message(message, thread_id)
            
            # Add password request flag to response
            if isinstance(result, dict):
                result["is_password_request"] = False
            else:
                logger.warning(f"OnboardingAssistant.send_message: Unexpected result type {type(result)} from parent send_message for user_id={self.user_id}")
                
            return result
            
        except Exception as e:
            logger.error(f"OnboardingAssistant.send_message: Unhandled error for user_id={self.user_id}, message='{message[:100]}...': {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant.send_message", 
                    "user_id": self.user_id,
                    "message_preview": message[:100],
                    "thread_id": thread_id,
                    "traceback": traceback.format_exc()
                })
            
            return {
                "status": "error", 
                "message": f"An error occurred during onboarding: {str(e)}", 
                "is_password_request": False
            }

    def stream_message(self, message: str, thread_id: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Override to handle password prompts but use parent's proven streaming logic.
        """
        try:
            is_guest = self._is_guest(self.user_id)
            
            # For onboarding, we need to check for password prompts after tool calls
            # We'll handle this by intercepting the stream and checking for password prompt conditions
            
            for event in super().stream_message(message, thread_id):
                # Forward all events from parent
                yield event
                
                # After response completes, check if we should prompt for password
                if event.get("type") == "response.completed":
                    try:
                        # Refresh session data to pick up any changes made by tool calls during this request
                        from custom_auth.models import OnboardingSession
                        try:
                            session = OnboardingSession.objects.filter(guest_id=str(self.user_id)).first()
                            if session:
                                session.refresh_from_db()
                        except Exception as refresh_error:
                            logger.warning(f"OnboardingAssistant.stream_message: Could not refresh session for user_id={self.user_id}: {refresh_error}")
                        
                        should_use_password_prompt = self._should_use_password_prompt()
                        yield {"type": "password_request", "is_password_request": should_use_password_prompt}
                    except Exception as password_check_error:
                        logger.error(f"OnboardingAssistant.stream_message: Error checking password prompt for user_id={self.user_id}: {password_check_error}", exc_info=True)
                        # n8n traceback
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        if n8n_traceback_url:
                            requests.post(n8n_traceback_url, json={
                                "error": str(password_check_error), 
                                "source": "OnboardingAssistant.stream_message.password_check", 
                                "user_id": self.user_id,
                                "traceback": traceback.format_exc()
                            })
                        # Yield safe default
                        yield {"type": "password_request", "is_password_request": False}
            
        except Exception as e:
            logger.error(f"OnboardingAssistant.stream_message: Unhandled error for user_id={self.user_id}, message='{message[:100]}...': {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant.stream_message", 
                    "user_id": self.user_id,
                    "message_preview": message[:100],
                    "thread_id": thread_id,
                    "traceback": traceback.format_exc()
                })
            
            # Yield error event
            yield {"type": "error", "message": f"Stream error: {str(e)}"}

    def _should_use_password_prompt(self) -> bool:
        """
        Determine if we should request a password prompt from the user.
        This should happen when onboarding_request_password tool was called and marked ready_for_password=True.
        """
        try:
            from custom_auth.models import OnboardingSession
            session = OnboardingSession.objects.filter(guest_id=str(self.user_id)).first()
            
            if not session or not session.data:
                return False
            
            data = session.data
            
            # Check if the onboarding_request_password tool was called and marked ready
            ready_for_password = bool(data.get('ready_for_password'))
            has_password = bool(data.get('password'))
            
            # Only prompt for password if:
            # 1. The onboarding_request_password tool marked us as ready AND
            # 2. We don't already have a password
            should_prompt = ready_for_password and not has_password
            
            return should_prompt
            
        except Exception as e:
            logger.error(f"OnboardingAssistant._should_use_password_prompt: Error checking password prompt for user_id={self.user_id}: {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant._should_use_password_prompt", 
                    "user_id": self.user_id,
                    "traceback": traceback.format_exc()
                })
            return False

    def reset_conversation(self) -> Dict[str, Any]:
        """Use parent's proven reset logic."""
        try:
            result = super().reset_conversation()
            return result
        except Exception as e:
            logger.error(f"OnboardingAssistant.reset_conversation: Error resetting conversation for user_id={self.user_id}: {str(e)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "OnboardingAssistant.reset_conversation", 
                    "user_id": self.user_id,
                    "traceback": traceback.format_exc()
                })
            return {"status": "error", "message": f"Error resetting conversation: {str(e)}"}

    # Remove all the custom methods that duplicated parent functionality:
    # - _get_onboarding_history() [now uses parent's guest state]
    # - _save_onboarding_history() [now uses parent's _store_guest_state]  
    # - _process_onboarding_stream() [now uses parent's _process_stream]
    # - _extract_response_text() [uses parent's _extract]
    # - _fix_onboarding_args() [uses parent's _fix_function_args]



# ────────────────────────────────────────────────────────────────────
#  Helper: replace Instacart hyperlinks with branded CTA (BeautifulSoup)
# ────────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────
#  Integration Factory Functions for Django Template Email Formatting
# ────────────────────────────────────────────────────────────────────

def create_django_template_format_function(openai_client):
    """
    Factory function to create the Django template-compatible email formatting function
    that can be used as a drop-in replacement for _format_text_for_email_body
    """
    formatter = DjangoTemplateEmailFormatter(openai_client)
    return formatter.format_text_for_email_body

def create_django_template_sections_function(openai_client):
    """
    Factory function to create the full Django template sections function
    for complete template integration
    """
    formatter = DjangoTemplateEmailFormatter(openai_client)
    return formatter.get_django_template_sections

# ────────────────────────────────────────────────────────────────────
#  Email Processing Helper Functions
# ────────────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────────
#  Helper: append UTM parameters to Instacart URLs
# ────────────────────────────────────────────────────────────────────
def _append_instacart_utm_params(url: str) -> str:
    """
    Append required UTM parameters to Instacart URLs for affiliate tracking.
    
    Args:
        url: The original Instacart URL
        
    Returns:
        URL with UTM parameters appended
    """
    utm_params = "utm_campaign=instacart-idp&utm_medium=affiliate&utm_source=instacart_idp&utm_term=partnertype-mediapartner&utm_content=campaignid-20313_partnerid-6356307"
    
    # Check if URL already has query parameters
    if "?" in url:
        # URL already has query parameters, append with &
        return f"{url}&{utm_params}"
    else:
        # URL doesn't have query parameters, append with ?
        return f"{url}?{utm_params}"

# ────────────────────────────────────────────────────────────────────
#  Helper: build branded Instacart CTA button
# ────────────────────────────────────────────────────────────────────
