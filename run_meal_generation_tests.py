#!/usr/bin/env python
"""
Quick smoke test runner for meal generation refactor.

This script runs the three specific test scenarios:
1. Unit test with dummy user and no expiring items
2. Retry loop simulation with network failure
3. Pydantic validation of GPT output
"""

import os
import sys
import django
from django.test import TestCase
from django.db import transaction

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')
django.setup()

# Import the test class
from tests.test_meal_generation_refactor import TestMealGenerationRefactor

def main():
    """Run the smoke tests."""
    print("🚀 Starting Meal Generation Refactor Smoke Tests...")
    print("=" * 60)
    
    # Create test instance
    test_instance = TestMealGenerationRefactor()
    
    try:
        # Setup test data
        with transaction.atomic():
            test_instance.setUp()
            
            # Run the three specific tests requested
            print("\n1️⃣ Testing: Unit test with dummy user and no expiring items")
            test_instance.test_unit_test_no_expiring_items()
            
            print("\n2️⃣ Testing: Retry loop simulation with network failure")
            test_instance.test_retry_loop_network_failure()
            
            print("\n3️⃣ Testing: Pydantic validation of GPT output")
            test_instance.test_pydantic_validation_success()
            test_instance.test_pydantic_validation_with_pantry_items()
            test_instance.test_pydantic_validation_invalid_json()
            
            print("\n🎯 Bonus: Integration test with pantry items")
            test_instance.test_integration_with_pantry_items()
            
        print("\n" + "=" * 60)
        print("🎉 ALL SMOKE TESTS PASSED!")
        print("✅ Your refactoring is working correctly")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 