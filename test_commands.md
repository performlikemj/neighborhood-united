# Meal Generation Refactor - Test Commands

## Quick Smoke Tests

### Option 1: Run with custom script
```bash
python run_meal_generation_tests.py
```

### Option 2: Run with pytest (recommended)
```bash
# Run all meal generation tests
pytest tests/test_meal_generation_refactor.py -v

# Run specific test methods
pytest tests/test_meal_generation_refactor.py::TestMealGenerationRefactor::test_unit_test_no_expiring_items -v
pytest tests/test_meal_generation_refactor.py::TestMealGenerationRefactor::test_retry_loop_network_failure -v
pytest tests/test_meal_generation_refactor.py::TestMealGenerationRefactor::test_pydantic_validation_success -v
```

### Option 3: Run with Django test runner
```bash
python manage.py test tests.test_meal_generation_refactor
```

## Test Coverage Summary

The test suite covers your three requested scenarios:

1. **Unit test with dummy user and no expiring items**
   - ✅ Tests `generate_meal_details` with empty pantry
   - ✅ Verifies GPT returns `used_pantry_items: []`
   - ✅ Confirms prompt includes "expiring pantry items: None"

2. **Retry loop simulation with network failure**
   - ✅ Simulates network timeout on first attempt
   - ✅ Verifies second attempt succeeds
   - ✅ Confirms prompt length stays constant between attempts

3. **Pydantic validation of GPT output**
   - ✅ Tests valid JSON with `MealOutputSchema.model_validate_json()`
   - ✅ Tests with pantry items included
   - ✅ Tests invalid JSON correctly raises errors

## Expected Test Output

When all tests pass, you should see:
```
✅ Test 1 PASSED: No expiring items handled correctly
✅ Test 2 PASSED: Retry loop with network failure handled correctly
✅ Test 3a PASSED: Pydantic validation successful for valid JSON
✅ Test 3b PASSED: Pydantic validation with pantry items successful
✅ Test 3c PASSED: Pydantic validation correctly rejects invalid JSON
✅ Integration test PASSED: Pantry items handled correctly in meal generation
🎉 ALL TESTS PASSED! Your refactoring is working correctly.
```

## Debugging Failed Tests

If any tests fail, check:
1. Django settings are properly configured
2. Database migrations are up to date
3. OpenAI client mocking is working correctly
4. Pydantic models match expected JSON structure
5. Function signatures match expected parameters 