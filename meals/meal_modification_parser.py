import json
import textwrap
import logging
import os
import requests
import traceback
from typing import List
try:
    from groq import Groq  # Groq client for inference
except Exception:
    Groq = None
from django.conf import settings
from meals.models import MealPlan, MealPlanMeal
from meals.pydantic_models import MealPlanModificationRequest
from shared.utils import get_groq_client
logger = logging.getLogger(__name__)

def _get_groq_client():
    try:
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key and Groq is not None:
            return Groq(api_key=api_key)
    except Exception:
        pass
    return None

def parse_modification_request(
    raw_prompt: str,
    meal_plan: MealPlan,
    *,
    model: str = "gpt-5-mini"
) -> MealPlanModificationRequest:
    """
    Convert a free-form user prompt into a structured MealPlanModificationRequest.

    Each MealPlanMeal row in the plan is surfaced to the LLM, which decides
    (per slot) whether the prompt implies any changes.
    """
    
    try:
        # 1. Build context block
        context_lines: List[str] = []
        
        meal_plan_meals = meal_plan.mealplanmeal_set.select_related("meal").all()
        
        for mpm in meal_plan_meals:
            line = f"{mpm.id} | {mpm.meal.name} on {mpm.day} {mpm.meal_type}"
            context_lines.append(line)
            
        context_block = "\n".join(context_lines)

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

        # Debug prints removed

        messages = [
            {"role": "developer", "content": system_msg},
            {"role": "user", "content": raw_prompt},
        ]

        # Get the schema for the MealPlanModificationRequest
        schema = MealPlanModificationRequest.model_json_schema()

        # 3. Call LLM with Structured Outputs (prefer Groq if configured)
        try:
            groq_client = _get_groq_client()

            if not groq_client:

                raise ValueError("Groq client not available - GROQ_API_KEY must be set")

            
                groq_messages = [
                    {"role": ("system" if m.get("role") == "developer" else m.get("role")), "content": m.get("content")}
                    for m in messages
                ]
                groq_resp = groq_client.chat.completions.create(
                    model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                    messages=groq_messages,
                    temperature=0.2,
                    top_p=1,
                    stream=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "meal_plan_mod_request_v2",
                            "schema": schema,
                        },
                    },
                )
                raw_json = groq_resp.choices[0].message.content or "{}"
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"parse_modification_request", "traceback": traceback.format_exc()})
            raise

        # 4. Validate & return
        try:
            # Debug prints removed
            parsed = MealPlanModificationRequest.model_validate_json(raw_json)
            
            # Handle missing should_remove values by coercing to False
            for slot in parsed.slots:
                slot.should_remove = bool(slot.should_remove)
                
            return parsed
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"parse_modification_request", "traceback": traceback.format_exc()})
            raise
            
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"parse_modification_request", "traceback": traceback.format_exc()})
        raise 
