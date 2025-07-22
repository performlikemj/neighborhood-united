#!/usr/bin/env python3
"""
Test script for enhanced email formatting with diagnostic logging

This script helps debug the Instacart button formatting and email header issues.
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')
django.setup()

# Now import Django modules
from meals.enhanced_email_processor import process_email_with_enhanced_formatting
from meals.meal_assistant_implementation import MealPlanningAssistant
from shared.utils import get_openai_client
import logging

# Setup logging to see diagnostic output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_instacart_formatting():
    """Test Instacart button formatting with diagnostic logging"""
    
    # Test email content with headers and Instacart link
    test_email_with_headers = """From: test@example.com
Date: Mon, 1 Jan 2024 12:00:00 GMT
Subject: Shopping list request

Hi, I need a shopping list for this week.

Here's your shopping list:

Instacart link:
https://customers.dev.instacart.tools/store/shopping_lists/5827424

— PRODUCE —
• Apples: 6 units
• Bananas: 3 bunches

Thanks!"""
    
    # Test email without headers but with Instacart
    test_email_clean = """Hi, I need a shopping list for this week.

Here's your shopping list:

Instacart link:
https://customers.dev.instacart.tools/store/shopping_lists/5827424

— PRODUCE —
• Apples: 6 units
• Bananas: 3 bunches

Thanks!"""

    print("="*80)
    print("TESTING ENHANCED EMAIL FORMATTING")
    print("="*80)
    
    try:
        # Get OpenAI client and assistant
        openai_client = get_openai_client()
        assistant = MealPlanningAssistant(user_id="1")  # Use a test user ID
        
        user_context = {
            'user_id': '1',
            'sender_email': 'test@example.com',
            'session_id': 'test_session',
            'message_count': 1,
            'user_language': 'en'
        }
        
        print("\n1. Testing email WITH headers:")
        print("-" * 40)
        result1 = process_email_with_enhanced_formatting(
            test_email_with_headers,
            openai_client,
            assistant,
            user_context=user_context
        )
        
        print(f"Result status: {result1.get('status')}")
        print(f"Main content length: {len(result1.get('email_body_main', ''))}")
        print(f"Data content length: {len(result1.get('email_body_data', ''))}")
        print(f"CSS classes: {result1.get('css_classes', [])}")
        
        if 'instacart' in result1.get('email_body_main', '').lower():
            print("✅ Instacart content found in main section")
        else:
            print("❌ No Instacart content in main section")
            
        print("\n2. Testing email WITHOUT headers:")
        print("-" * 40)
        result2 = process_email_with_enhanced_formatting(
            test_email_clean,
            openai_client,
            assistant,
            user_context=user_context
        )
        
        print(f"Result status: {result2.get('status')}")
        print(f"Main content length: {len(result2.get('email_body_main', ''))}")
        print(f"Data content length: {len(result2.get('email_body_data', ''))}")
        print(f"CSS classes: {result2.get('css_classes', [])}")
        
        if 'instacart' in result2.get('email_body_main', '').lower():
            print("✅ Instacart content found in main section")
        else:
            print("❌ No Instacart content in main section")
            
        # Check for button HTML
        for i, result in enumerate([result1, result2], 1):
            main_content = result.get('email_body_main', '')
            if '<a href=' in main_content and 'instacart' in main_content.lower():
                print(f"✅ Test {i}: Instacart button HTML detected")
            else:
                print(f"❌ Test {i}: No Instacart button HTML found")
                
        print("\n" + "="*80)
        print("DIAGNOSTIC COMPLETE - Check logs above for detailed tracing")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_instacart_formatting() 