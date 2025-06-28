import json
import textwrap
import logging
from typing import List
from openai import OpenAI
from django.conf import settings
from meals.models import MealPlan, MealPlanMeal
from meals.pydantic_models import MealPlanModificationRequest
from shared.utils import get_openai_client
logger = logging.getLogger(__name__)

def parse_modification_request(
    raw_prompt: str,
    meal_plan: MealPlan,
    *,
    model: str = "gpt-4.1-mini"
) -> MealPlanModificationRequest:
    """
    Convert a free-form user prompt into a structured MealPlanModificationRequest.

    Each MealPlanMeal row in the plan is surfaced to the LLM, which decides
    (per slot) whether the prompt implies any changes.
    """
    print(f"DEBUG parse_modification_request: Starting with prompt={raw_prompt}, meal_plan_id={meal_plan.id}")
    
    try:
        # 1. Build context block
        context_lines: List[str] = []
        print(f"DEBUG parse_modification_request: Building context from meal plan meals")
        
        meal_plan_meals = meal_plan.mealplanmeal_set.select_related("meal").all()
        print(f"DEBUG parse_modification_request: Found {len(meal_plan_meals)} meals in the plan")
        
        for mpm in meal_plan_meals:
            line = f"{mpm.id} | {mpm.meal.name} on {mpm.day} {mpm.meal_type}"
            context_lines.append(line)
            print(f"DEBUG parse_modification_request: Added line: {line}")
            
        context_block = "\n".join(context_lines)
        print(f"DEBUG parse_modification_request: Context block built with {len(context_lines)} lines")

        # 2. Compose messages
        system_msg = textwrap.dedent(
            f"""
            You convert meal-plan change requests into JSON, obeying a strict schema.
            For every slot listed below, decide whether the user's request demands
            changes.  If no change is needed, output an empty "change_rules" array.

            CURRENT MEAL PLAN (one per line):
            meal_plan_meal_id | meal name | slot
            ------------------------------------------------
            {context_block}
            ------------------------------------------------
            IMPORTANT:
              • Resolve relative dates like "this Saturday" to absolute weekday names.
              • Do NOT invent slot IDs; only use the IDs given.
              • Use the provided JSON-Schema exactly – no additional keys, no prose.
              • For each meal slot, you MUST include the change_rules array, even if it's empty ([]).
              • Always return change_rules as an array, never null or omitted.
              • Set `should_remove: true` for any meal that should be completely removed without replacement.
                This applies when the user explicitly asks to remove a meal rather than replace it (e.g.,
                "remove dinner on Monday", "delete Thursday's breakfast"). Otherwise, keep it as `false`.
            """
        ).strip()

        messages = [
            {"role": "developer", "content": system_msg},
            {"role": "user", "content": raw_prompt},
        ]
        print(f"DEBUG parse_modification_request: Messages prepared, system msg length: {len(system_msg)}")

        # Get the schema for the MealPlanModificationRequest
        schema = MealPlanModificationRequest.model_json_schema()
        print(f"DEBUG parse_modification_request: Got schema: {json.dumps(schema)[:200]}...")

        # 3. Call Responses API with Structured Outputs
        print(f"DEBUG parse_modification_request: About to call OpenAI")
        try:
            resp = get_openai_client().responses.create(
                model=model,
                input=messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "meal_plan_mod_request_v2",
                        "schema": schema,
                    }
                },
            )
            print(f"DEBUG parse_modification_request: Got response from OpenAI: {resp.output_text[:200]}...")
        except Exception as e:
            import traceback
            print(f"DEBUG parse_modification_request: Error from OpenAI API: {str(e)}")
            print(f"DEBUG parse_modification_request: Traceback: {traceback.format_exc()}")
            raise

        # 4. Validate & return
        try:
            parsed = MealPlanModificationRequest.model_validate_json(resp.output_text)
            print(f"DEBUG parse_modification_request: Validated response, got {len(parsed.slots)} slots")
            
            # Handle missing should_remove values by coercing to False
            for slot in parsed.slots:
                slot.should_remove = bool(slot.should_remove)
                
            # Print details of each slot
            for i, slot in enumerate(parsed.slots):
                print(f"DEBUG parse_modification_request: Slot {i+1}: id={slot.meal_plan_meal_id}, name={slot.meal_name}, rules={slot.change_rules}")
                
            logger.debug("Parsed MealPlanModificationRequest: %s", parsed.model_dump())
            return parsed
        except Exception as e:
            import traceback
            print(f"DEBUG parse_modification_request: Error validating response: {str(e)}")
            print(f"DEBUG parse_modification_request: Response text: {resp.output_text}")
            print(f"DEBUG parse_modification_request: Traceback: {traceback.format_exc()}")
            raise
            
    except Exception as e:
        import traceback
        print(f"DEBUG parse_modification_request: Unexpected error: {str(e)}")
        print(f"DEBUG parse_modification_request: Traceback: {traceback.format_exc()}")
        raise 