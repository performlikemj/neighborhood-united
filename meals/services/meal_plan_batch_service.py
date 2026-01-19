"""Service layer for Groq batch-based weekly meal plan generation."""
from __future__ import annotations

import io
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Optional, Sequence

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import (
    MealPlanBatchJob,
    MealPlanBatchRequest,
    MealPlan,
    MealPlanMeal,
    Meal,
    PantryItem,
    MealPlanMealPantryUsage,
    DietaryPreference,
)
from meals.meal_generation import determine_usage_for_meal
from meals.services.meal_plan_batching import MealPlanBatchRequestBuilder, generate_batch_entries
from pydantic import BaseModel, Field, ValidationError, ConfigDict

logger = logging.getLogger(__name__)

DAY_NAME_TO_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class BatchProcessingError(Exception):
    """Raised when applying a batch response fails and requires fallback."""


class ChatCompletionMessage(BaseModel):
    role: str
    content: str
    model_config = ConfigDict(extra="ignore")


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatCompletionMessage
    model_config = ConfigDict(extra="ignore")


class ChatCompletionBody(BaseModel):
    choices: List[ChatCompletionChoice] = Field(default_factory=list)
    model_config = ConfigDict(extra="ignore")


class GroqBatchResponse(BaseModel):
    status_code: int
    body: ChatCompletionBody
    model_config = ConfigDict(extra="ignore")


@dataclass
class ParsedSlot:
    day: str
    meal_type: str
    notes: Optional[str] = None


def _get_groq_client():
    try:
        from groq import Groq  # type: ignore
    except Exception:  # pragma: no cover - library unavailable in some envs
        return None

    api_key = getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to instantiate Groq client: %s", exc)
        return None


def submit_weekly_batch(
    *,
    week_start: date,
    week_end: date,
    completion_window: str = "24h",
    request_id: Optional[str] = None,
) -> Optional[MealPlanBatchJob]:
    """Submit a Groq batch covering all auto-enabled users.

    Returns the persisted job or ``None`` when we fall back to synchronous generation.
    """
    # Check if a batch job already exists for this week to prevent duplicates
    existing_job = MealPlanBatchJob.objects.filter(
        week_start_date=week_start,
        week_end_date=week_end,
    ).exclude(
        status__in=[MealPlanBatchJob.STATUS_FAILED, MealPlanBatchJob.STATUS_EXPIRED]
    ).first()
    
    if existing_job:
        logger.info(
            "Batch job already exists for week %s-%s (job %s, status=%s). Skipping duplicate submission.",
            week_start,
            week_end,
            existing_job.id,
            existing_job.status,
        )
        return existing_job
    
    users = list(_eligible_users())
    if not users:
        logger.info("No auto-enabled users to include in weekly batch %s-%s", week_start, week_end)
        return None

    payload_builder = MealPlanBatchRequestBuilder()
    payload = payload_builder.build_payload(
        users=users,
        week_start=week_start,
        week_end=week_end,
        request_id=request_id,
    )

    groq_client = _get_groq_client()
    if not groq_client:
        logger.warning("Groq client unavailable; falling back to synchronous weekly generation")
        _schedule_synchronous_generation(users, week_start, week_end)
        return None

    try:
        with tempfile.NamedTemporaryFile("w+b", suffix=".jsonl", delete=False) as temp_file:
            data = payload if payload.endswith("\n") else f"{payload}\n"
            temp_file.write(data.encode("utf-8"))
            temp_file.flush()
            temp_path = temp_file.name

        with open(temp_path, "rb") as fh:
            file_resp = groq_client.files.create(
                file=("meal_plan_batch.jsonl", fh),
                purpose="batch",
            )
        input_file_id = getattr(file_resp, "id", None)
        if not input_file_id:
            raise RuntimeError("Groq files.create response missing id")

        batch_resp = groq_client.batches.create(
            completion_window=completion_window,
            endpoint="/v1/chat/completions",
            input_file_id=input_file_id,
        )
        batch_id = getattr(batch_resp, "id", None)
        if not batch_id:
            raise RuntimeError("Groq batches.create response missing id")
    except Exception as exc:
        logger.exception("Failed to submit Groq batch: %s", exc)
        _schedule_synchronous_generation(users, week_start, week_end)
        return None
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

    with transaction.atomic():
        job = MealPlanBatchJob.objects.create(
            week_start_date=week_start,
            week_end_date=week_end,
            status=MealPlanBatchJob.STATUS_SUBMITTED,
            completion_window=completion_window,
            batch_id=batch_id,
            input_file_id=input_file_id,
        )
        job.register_members(generate_batch_entries(users, week_start))

    logger.info(
        "Submitted Groq batch %s for %d users (week %s-%s)",
        batch_id,
        len(users),
        week_start,
        week_end,
    )
    return job


def process_batch_job(job_id: int) -> None:
    """Sync Groq batch status, parse outputs, and schedule fallbacks when needed."""
    job = MealPlanBatchJob.objects.get(id=job_id)

    groq_client = _get_groq_client()
    if not groq_client:
        logger.error("Groq client unavailable while processing job %s; falling back", job_id)
        _mark_job_failed_and_fallback(job, "groq_client_unavailable")
        return

    try:
        batch_obj = groq_client.batches.retrieve(job.batch_id)
    except Exception as exc:
        logger.exception("Failed to retrieve batch %s: %s", job.batch_id, exc)
        _mark_job_failed_and_fallback(job, f"retrieve_error:{exc}")
        return

    status = getattr(batch_obj, "status", "unknown")
    logger.info("Job %s Groq status=%s", job.id, status)

    if status in {"validating", "submitted"}:
        job.status = MealPlanBatchJob.STATUS_SUBMITTED
        job.save(update_fields=["status", "updated_at"])
        return
    if status == "in_progress":
        job.status = MealPlanBatchJob.STATUS_IN_PROGRESS
        job.save(update_fields=["status", "updated_at"])
        return
    if status == "failed":
        reason = json.dumps(getattr(batch_obj, "errors", "")) if getattr(batch_obj, "errors", None) else "groq_failed"
        _mark_job_failed_and_fallback(job, reason)
        _record_batch_metrics(job, event="failed")
        return
    if status == "expired":
        job.mark_expired("groq_batch_expired")
        _schedule_fallback_for_requests(job)
        _record_batch_metrics(job, event="expired")
        return
    if status != "completed":
        logger.warning("Unexpected Groq batch status %s for job %s", status, job.id)
        return

    output_file_id = getattr(batch_obj, "output_file_id", None)
    job.output_file_id = output_file_id
    job.error_file_id = getattr(batch_obj, "error_file_id", None)

    if not output_file_id:
        logger.warning("Job %s completed without output_file_id; scheduling fallback", job.id)
        job.mark_failed("missing_output_file")
        _schedule_fallback_for_requests(job)
        return

    lines = _download_jsonl(groq_client, output_file_id)
    _apply_batch_results(job, lines)

    job.status = MealPlanBatchJob.STATUS_COMPLETED
    job.save(update_fields=["status", "output_file_id", "error_file_id", "updated_at"])

    pending = job.users_requiring_fallback()
    if pending:
        logger.info("Job %s completed but %d users require fallback", job.id, len(pending))
        _schedule_fallback_for_requests(job, user_ids=pending)
        _record_batch_metrics(job, event="completed_with_fallbacks")
    else:
        _record_batch_metrics(job, event="completed")


def _eligible_users() -> Iterable[CustomUser]:
    return CustomUser.objects.filter(auto_meal_plans_enabled=True, is_active=True)


def _schedule_synchronous_generation(
    users: Sequence[CustomUser],
    week_start: date,
    week_end: date,
) -> None:
    from meals.meal_plan_service import create_meal_plan_for_user

    for user in users:
        create_meal_plan_for_user(
            user_id=user.id,
            start_of_week=week_start,
            end_of_week=week_end,
        )


def _schedule_fallback_for_requests(job: MealPlanBatchJob, user_ids: Optional[Sequence[int]] = None) -> None:
    if user_ids is None:
        user_ids = list(job.requests.values_list("user_id", flat=True))
    job.requests.filter(user_id__in=user_ids).update(
        status=MealPlanBatchRequest.STATUS_FALLBACK,
        completed_at=timezone.now(),
    )
    users = CustomUser.objects.filter(id__in=user_ids)
    _schedule_synchronous_generation(list(users), job.week_start_date, job.week_end_date)


def _mark_job_failed_and_fallback(job: MealPlanBatchJob, reason: str) -> None:
    job.mark_failed(reason)
    _schedule_fallback_for_requests(job)
    _record_batch_metrics(job, event="failed")


def _download_jsonl(client, file_id: str) -> List[str]:
    try:
        resp = client.files.content(file_id)
    except Exception as exc:
        logger.exception("Failed to fetch Groq batch output %s: %s", file_id, exc)
        return []

    if hasattr(resp, "write_to_file"):
        with tempfile.NamedTemporaryFile("w+b", delete=False) as fh:
            temp_path = fh.name
        try:
            resp.write_to_file(temp_path)
            with open(temp_path, "r", encoding="utf-8") as reader:
                return reader.read().splitlines()
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    if hasattr(resp, "content"):
        content = getattr(resp, "content")
        if isinstance(content, (bytes, bytearray)):
            return io.BytesIO(content).read().decode("utf-8").splitlines()
        if isinstance(content, str):
            return content.splitlines()

    logger.warning("Unable to interpret Groq file response for %s", file_id)
    return []


def _apply_batch_results(job: MealPlanBatchJob, lines: Sequence[str]) -> None:
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            logger.error("Invalid JSONL line in batch job %s: %s", job.id, line)
            continue
        custom_id = payload.get("custom_id")
        if not custom_id:
            logger.error("Batch line missing custom_id: %s", payload)
            continue
        try:
            request_obj = job.requests.select_related("user").get(custom_id=custom_id)
        except MealPlanBatchRequest.DoesNotExist:
            logger.warning("Received response for unknown custom_id %s", custom_id)
            continue

        response_payload = payload.get("response") or {}
        
        # Handle null from batch response
        if response_payload is None:
            logger.warning("Batch response payload is null for %s", custom_id)
            job.mark_request_failed(custom_id=custom_id, error_message="null_response")
            _schedule_fallback_for_requests(job, user_ids=[request_obj.user_id])
            continue
        
        try:
            groq_response = GroqBatchResponse.model_validate(response_payload)
        except ValidationError as exc:
            logger.warning("Batch response validation failed for %s: %s", custom_id, exc)
            job.mark_request_failed(custom_id=custom_id, error_message="validation_error")
            _schedule_fallback_for_requests(job, user_ids=[request_obj.user_id])
            continue

        if groq_response.status_code != 200:
            logger.warning(
                "Groq response for %s returned status %s; scheduling fallback",
                custom_id,
                groq_response.status_code,
            )
            job.mark_request_failed(
                custom_id=custom_id,
                error_message=f"http_{groq_response.status_code}",
            )
            _schedule_fallback_for_requests(job, user_ids=[request_obj.user_id])
            continue

        try:
            plan_dict, parsed_slots = _extract_plan_from_response(groq_response)
            _apply_plan_for_user(
                job=job,
                request_obj=request_obj,
                plan_dict=plan_dict,
                slots=parsed_slots,
            )
        except BatchProcessingError as exc:
            logger.warning(
                "Applying batch plan failed for %s: %s. Falling back to sync generation.",
                custom_id,
                exc,
            )
            job.mark_request_failed(custom_id=custom_id, error_message=str(exc))
            _schedule_fallback_for_requests(job, user_ids=[request_obj.user_id])
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected error applying batch plan for %s", custom_id)
            job.mark_request_failed(custom_id=custom_id, error_message=f"unexpected:{exc}")
            _schedule_fallback_for_requests(job, user_ids=[request_obj.user_id])
        else:
            job.mark_request_completed(custom_id=custom_id, response_payload=response_payload)


def _apply_plan_for_user(
    *,
    job: MealPlanBatchJob,
    request_obj: MealPlanBatchRequest,
    plan_dict: dict,
    slots: List[ParsedSlot],
) -> None:
    user = request_obj.user
    week_start = job.week_start_date
    week_end = job.week_end_date
    request_id = f"batch-{job.id}-{request_obj.custom_id}"
    user_prompt = plan_dict.get("user_prompt") if isinstance(plan_dict, dict) else None

    with transaction.atomic():
        meal_plan, _ = MealPlan.objects.select_for_update().get_or_create(
            user=user,
            week_start_date=week_start,
            week_end_date=week_end,
            defaults={
                "is_approved": False,
                "has_changes": False,
            },
        )

        # Reset existing slots for deterministic behaviour
        MealPlanMeal.objects.filter(meal_plan=meal_plan).delete()

        slots_applied = 0
        for slot in slots:
            _apply_slot_to_plan(
                user=user,
                meal_plan=meal_plan,
                slot=slot,
                request_id=request_id,
                user_prompt=user_prompt,
            )
            slots_applied += 1

        if slots_applied == 0:
            raise BatchProcessingError("no_meals_returned")

    _finalize_meal_plan(user=user, meal_plan=meal_plan, request_id=request_id)


def _apply_slot_to_plan(
    *,
    user: CustomUser,
    meal_plan: MealPlan,
    slot: ParsedSlot,
    request_id: str,
    user_prompt: Optional[str],
) -> None:
    day_index = DAY_NAME_TO_INDEX.get(slot.day.lower())
    if day_index is None:
        raise BatchProcessingError(f"invalid_day:{slot.day}")

    meal_date = meal_plan.week_start_date + timedelta(days=day_index)
    if meal_date < meal_plan.week_start_date or meal_date > meal_plan.week_end_date:
        raise BatchProcessingError(f"day_out_of_range:{slot.day}")

    meal_type = slot.meal_type.capitalize()
    valid_types = {choice for choice, _ in Meal.MEAL_TYPE_CHOICES}
    if meal_type not in valid_types:
        raise BatchProcessingError(f"invalid_meal_type:{slot.meal_type}")

    meal = _ensure_meal_from_slot(user=user, meal_type=meal_type, slot=slot, user_prompt=user_prompt)

    if not _run_sanity_checks(user=user, meal=meal, request_id=request_id):
        raise BatchProcessingError("sanity_check_failed")

    meal_plan_meal, _ = MealPlanMeal.objects.update_or_create(
        meal_plan=meal_plan,
        day=meal_date.strftime("%A"),
        meal_type=meal_type,
        defaults={
            "meal": meal,
            "meal_date": meal_date,
        },
    )

    _update_pantry_usage(user=user, meal_plan_meal=meal_plan_meal, slot=slot, request_id=request_id)


def _derive_meal_name(slot: ParsedSlot) -> str:
    note = (slot.notes or "").strip()
    if note:
        first_sentence = note.split('.')[0].strip()
        if first_sentence:
            return first_sentence[:100]
    return f"{slot.day} {slot.meal_type} Idea"


def _ensure_meal_from_slot(*, user: CustomUser, meal_type: str, slot: ParsedSlot, user_prompt: Optional[str]) -> Meal:
    note = (slot.notes or "").strip()
    name = _derive_meal_name(slot)

    meal = Meal.objects.filter(creator=user, name=name).first()

    description_parts = [note] if note else []
    description = "\n\n".join(description_parts) or name

    if meal is None:
        meal = Meal.objects.create(
            name=name,
            description=description,
            meal_type=meal_type,
            creator=user,
        )
    else:
        meal.description = description
        meal.meal_type = meal_type
        meal.save(update_fields=["description", "meal_type"])

    return meal


def _run_sanity_checks(*, user: CustomUser, meal: Meal, request_id: str) -> bool:
    from meals.meal_plan_service import perform_comprehensive_sanity_check

    try:
        return perform_comprehensive_sanity_check(meal, user, request_id=request_id)
    except Exception as exc:
        logger.exception("Sanity check crashed for meal %s: %s", meal.id, exc)
        return False


def _update_pantry_usage(
    *,
    user: CustomUser,
    meal_plan_meal: MealPlanMeal,
    slot: ParsedSlot,
    request_id: str,
) -> None:
    # Batch results do not currently include pantry usage data
    return


def _finalize_meal_plan(*, user: CustomUser, meal_plan: MealPlan, request_id: str) -> None:
    from meals.meal_plan_service import analyze_and_replace_meals

    meal_types = [choice for choice, _ in Meal.MEAL_TYPE_CHOICES]
    analyze_and_replace_meals(user, meal_plan, meal_types, request_id)

    first_groq_approval = meal_plan.groq_auto_approved_at is None
    if first_groq_approval:
        meal_plan.groq_auto_approved_at = timezone.now()
        if hasattr(meal_plan, "_suppress_auto_approval_email"):
            delattr(meal_plan, "_suppress_auto_approval_email")
    else:
        meal_plan._suppress_auto_approval_email = True

    meal_plan.is_approved = True
    meal_plan.has_changes = False
    update_fields = ["is_approved", "has_changes"]
    if first_groq_approval:
        update_fields.append("groq_auto_approved_at")
    meal_plan.save(update_fields=update_fields)


def _extract_plan_from_response(groq_response: GroqBatchResponse) -> tuple[dict, List[ParsedSlot]]:
    if not groq_response.body.choices:
        raise BatchProcessingError("no_choices")

    content = groq_response.body.choices[0].message.content
    if not content:
        raise BatchProcessingError("empty_content")

    try:
        plan_dict = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BatchProcessingError(f"invalid_json:{exc}") from exc

    if not isinstance(plan_dict, dict):
        raise BatchProcessingError("plan_not_dict")

    slots_data = plan_dict.get("slots")
    if not isinstance(slots_data, list):
        raise BatchProcessingError("slots_missing")

    parsed_slots: List[ParsedSlot] = []
    for item in slots_data:
        if not isinstance(item, dict):
            continue
        day = item.get("day")
        meal_type = item.get("meal_type")
        if not isinstance(day, str) or not isinstance(meal_type, str):
            continue
        notes = item.get("notes") if isinstance(item.get("notes"), str) else None
        parsed_slots.append(ParsedSlot(day=day, meal_type=meal_type, notes=notes))

    if not parsed_slots:
        raise BatchProcessingError("no_valid_slots")

    return plan_dict, parsed_slots


def _record_batch_metrics(job: MealPlanBatchJob, event: str) -> None:
    try:
        from django.db.models import Count, Q

        request_counts = job.requests.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=MealPlanBatchRequest.STATUS_COMPLETED)),
            failed=Count("id", filter=Q(status=MealPlanBatchRequest.STATUS_FAILED)),
            fallback=Count("id", filter=Q(status=MealPlanBatchRequest.STATUS_FALLBACK)),
            pending=Count("id", filter=Q(status=MealPlanBatchRequest.STATUS_PENDING)),
        )

        logger.info(
            "meal_plan_batch_metrics",
            extra={
                "event": event,
                "job_id": job.id,
                "status": job.status,
                "batch_id": job.batch_id,
                "week_start": job.week_start_date.isoformat() if job.week_start_date else None,
                "week_end": job.week_end_date.isoformat() if job.week_end_date else None,
                "requests": request_counts,
            },
        )
    except Exception as exc:  # pragma: no cover - metrics logging should not crash processing
        logger.debug("Failed to record batch metrics for job %s: %s", job.id, exc)
