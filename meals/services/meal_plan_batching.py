"""Utilities for building and tracking Groq batch meal-plan requests."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Sequence, Tuple

from django.conf import settings

from custom_auth.models import CustomUser
from shared.utils import generate_user_context


@dataclass(frozen=True)
class MealPlanBatchRequest:
    """Lightweight value object representing one JSONL request line."""

    custom_id: str
    method: str
    url: str
    body: dict

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "custom_id": self.custom_id,
                "method": self.method,
                "url": self.url,
                "body": self.body,
            }
        )


class MealPlanBatchRequestBuilder:
    """Builds Groq JSONL payloads for weekly meal plan generation."""

    def __init__(self, *, model: str | None = None):
        self.model = model or getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")

    def build_payload(
        self,
        *,
        users: Sequence[CustomUser],
        week_start: date,
        week_end: date,
        request_id: str | None = None,
    ) -> str:
        """Return newline-delimited JSON (JSONL) for a Groq batch submission."""
        requests = [
            self._build_request_for_user(user, week_start, week_end, request_id)
            for user in users
        ]
        return "\n".join(req.to_jsonl() for req in requests)

    # --- private helpers -------------------------------------------------
    def _build_request_for_user(
        self,
        user: CustomUser,
        week_start: date,
        week_end: date,
        request_id: str | None,
    ) -> MealPlanBatchRequest:
        custom_id = self._custom_id(user, week_start)
        body = {
            "model": self.model,
            "temperature": 0.2,
            "top_p": 1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meal_map",
                    "schema": self._prompt_schema_name(),
                },
            },
            "messages": self._build_messages(user, week_start, week_end, request_id),
        }
        return MealPlanBatchRequest(
            custom_id=custom_id,
            method="POST",
            url="/v1/chat/completions",
            body=body,
        )

    def _build_messages(
        self,
        user: CustomUser,
        week_start: date,
        week_end: date,
        request_id: str | None,
    ) -> List[dict]:
        system_content = (
            "You are SautAI, a meal-planning expert who creates detailed weekly meal plans "
            "with clear structure and JSON output compatible with the PromptMealMap schema."
        )

        developer_content = (
            "Generate a structured weekly meal plan JSON payload. Always honour dietary preferences, "
            "allergies, and household context. Avoid repeating meals from the last few weeks."
        )

        user_goal_description = getattr(getattr(user, "goals", None), "goal_description", "").strip()
        if user_goal_description:
            goal_line = f"User goal: {user_goal_description}."
        else:
            goal_line = ""

        household_context = generate_user_context(user)

        user_content = (
            f"Create a complete meal plan for the upcoming week running {week_start.isoformat()} to "
            f"{week_end.isoformat()}. {goal_line}\n"
            f"Use household context: {household_context}.\n"
            "Return JSON following the PromptMealMap schema with day and meal_type slots."
        )

        if request_id:
            request_suffix = f" Request id: {request_id}."
            user_content += request_suffix

        return [
            {"role": "system", "content": system_content},
            {"role": "developer", "content": developer_content},
            {"role": "user", "content": user_content},
        ]

    def _prompt_schema_name(self) -> dict:
        from meals.pydantic_models import PromptMealMap

        return PromptMealMap.model_json_schema()

    @staticmethod
    def _custom_id(user: CustomUser, week_start: date) -> str:
        return f"plan-{user.id}-{week_start.isoformat()}"


def generate_batch_entries(
    users: Iterable[CustomUser],
    week_start: date,
) -> List[Tuple[int, str]]:
    """Return [(user_id, custom_id), ...] for use when registering batch members."""
    return [
        (user.id, MealPlanBatchRequestBuilder._custom_id(user, week_start))
        for user in users
    ]
