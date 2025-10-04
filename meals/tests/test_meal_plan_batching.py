import json
from datetime import date, timedelta

import pytest

from custom_auth.models import CustomUser
from meals.models import MealPlanBatchJob, MealPlanBatchRequest, MealPlan, MealPlanMeal
from meals.services.meal_plan_batching import MealPlanBatchRequestBuilder
from meals.services import meal_plan_batch_service


@pytest.mark.django_db
def test_build_batch_payload_includes_upcoming_week_context(settings):

    settings.TEST_MODE = True
    user = CustomUser.objects.create_user(
        username="batchtester",
        password="pass1234",
        email="batch@example.com",
        auto_meal_plans_enabled=True,
    )

    week_start = date(2025, 9, 29)
    week_end = week_start + timedelta(days=6)

    builder = MealPlanBatchRequestBuilder(model="llama-3.1-8b-instant")
    payload = builder.build_payload(
        users=[user],
        week_start=week_start,
        week_end=week_end,
        request_id="batch-test",
    )

    lines = payload.strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["custom_id"] == f"plan-{user.id}-2025-09-29"
    assert record["method"] == "POST"
    assert record["url"] == "/v1/chat/completions"
    assert record["body"]["model"] == "llama-3.1-8b-instant"

    messages = record["body"]["messages"]
    assert any(m["role"] == "system" for m in messages)
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "2025-09-29" in user_msg["content"]
    assert "upcoming week" in user_msg["content"].lower()


@pytest.mark.django_db
def test_batch_job_tracks_members_and_pending_status():
    user1 = CustomUser.objects.create_user(
        username="batchuser1",
        password="pass123",
        email="batch1@example.com",
    )
    user2 = CustomUser.objects.create_user(
        username="batchuser2",
        password="pass123",
        email="batch2@example.com",
    )

    week_start = date(2025, 9, 29)
    week_end = week_start + timedelta(days=6)

    job = MealPlanBatchJob.objects.create(
        week_start_date=week_start,
        week_end_date=week_end,
    )
    job.register_members([
        (user1.id, f"plan-{user1.id}-2025-09-29"),
        (user2.id, f"plan-{user2.id}-2025-09-29"),
    ])

    assert job.requests.count() == 2

    job.mark_request_completed(
        custom_id=f"plan-{user1.id}-2025-09-29",
        response_payload={"status_code": 200},
    )

    pending_ids = job.pending_user_ids()
    assert pending_ids == [user2.id]

    job.mark_failed("timeout")
    assert job.status == MealPlanBatchJob.STATUS_FAILED
    assert set(job.users_requiring_fallback()) == {user1.id, user2.id}


@pytest.mark.django_db
def test_submit_weekly_batch_registers_users_and_calls_groq(monkeypatch, settings):
    settings.TEST_MODE = True

    users = [
        CustomUser.objects.create_user(username="one", password="pass", email="one@example.com"),
        CustomUser.objects.create_user(username="two", password="pass", email="two@example.com"),
    ]
    for user in users:
        user.auto_meal_plans_enabled = True
        user.save(update_fields=["auto_meal_plans_enabled"])

    week_start = date(2025, 9, 29)
    week_end = week_start + timedelta(days=6)

    created_batches = {}

    class FakeFiles:
        def create(self, file, purpose):
            created_batches["file_called"] = True
            return type("FileResp", (), {"id": "file_123"})()

        def content(self, file_id):
            raise AssertionError("content() should not be called in submission test")

    class FakeBatches:
        def create(self, **kwargs):
            created_batches["batch_called"] = True
            return type("BatchResp", (), {"id": "batch_123", "status": "submitted", "endpoint": kwargs.get("endpoint")})()

        def retrieve(self, batch_id):
            raise AssertionError("retrieve() should not be called in submission test")

    fake_client = type("FakeGroq", (), {"files": FakeFiles(), "batches": FakeBatches()})()

    monkeypatch.setattr(meal_plan_batch_service, "_get_groq_client", lambda: fake_client)

    job = meal_plan_batch_service.submit_weekly_batch(
        week_start=week_start,
        week_end=week_end,
        request_id="test",
    )

    assert job is not None
    assert created_batches["file_called"]
    assert created_batches["batch_called"]
    job.refresh_from_db()
    assert job.status == MealPlanBatchJob.STATUS_SUBMITTED
    assert job.requests.count() == 2
    custom_ids = set(job.requests.values_list("custom_id", flat=True))
    expected_ids = {f"plan-{user.id}-2025-09-29" for user in users}
    assert custom_ids == expected_ids


@pytest.mark.django_db
def test_submit_weekly_batch_without_client_triggers_fallback(monkeypatch):
    users = [
        CustomUser.objects.create_user(username="sync-one", password="pass", email="one@example.com"),
        CustomUser.objects.create_user(username="sync-two", password="pass", email="two@example.com"),
    ]

    for user in users:
        user.auto_meal_plans_enabled = True
        user.save(update_fields=["auto_meal_plans_enabled"])

    monkeypatch.setattr(meal_plan_batch_service, "_get_groq_client", lambda: None)
    triggered = []

    def fake_schedule(users, week_start, week_end):
        triggered.extend([user.id for user in users])

    monkeypatch.setattr(
        meal_plan_batch_service,
        "_schedule_synchronous_generation",
        fake_schedule,
    )

    job = meal_plan_batch_service.submit_weekly_batch(
        week_start=date(2025, 9, 29),
        week_end=date(2025, 10, 5),
        request_id="no-groq",
    )

    assert job is None
    assert set(triggered) == {user.id for user in users}


@pytest.mark.django_db
def test_process_batch_job_handles_completed_output(monkeypatch):
    user = CustomUser.objects.create_user(username="ready", password="pass", email="ready@example.com")
    job = MealPlanBatchJob.objects.create(
        week_start_date=date(2025, 9, 29),
        week_end_date=date(2025, 10, 5),
        status=MealPlanBatchJob.STATUS_SUBMITTED,
        batch_id="batch_789",
        input_file_id="file_in",
    )
    request = MealPlanBatchRequest.objects.create(
        job=job,
        user=user,
        custom_id=f"plan-{user.id}-2025-09-29",
    )

    class FakeFiles:
        def content(self, file_id):
            class Resp:
                def write_to_file(self, path):
                    plan_payload = {
                        "user_prompt": "Test prompt",
                        "slots": [
                            {
                                "day": "Monday",
                                "meal_type": "Breakfast",
                                "notes": "Batch oatmeal with berries",
                            }
                        ],
                    }
                    payload = {
                        "custom_id": request.custom_id,
                        "response": {
                            "status_code": 200,
                            "body": {
                                "choices": [
                                    {
                                        "index": 0,
                                        "message": {
                                            "role": "assistant",
                                            "content": json.dumps(plan_payload),
                                        },
                                    }
                                ]
                            },
                        },
                    }
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(json.dumps(payload) + "\n")

                @property
                def content(self):
                    plan_payload = {
                        "user_prompt": "Test prompt",
                        "slots": [
                            {
                                "day": "Monday",
                                "meal_type": "Breakfast",
                                "notes": "Batch oatmeal with berries",
                            }
                        ],
                    }
                    return json.dumps({
                        "custom_id": request.custom_id,
                        "response": {
                            "status_code": 200,
                            "body": {
                                "choices": [
                                    {
                                        "index": 0,
                                        "message": {
                                            "role": "assistant",
                                            "content": json.dumps(plan_payload),
                                        },
                                    }
                                ]
                            },
                        },
                    })

            return Resp()

        def create(self, *args, **kwargs):
            raise AssertionError

    class FakeBatches:
        def retrieve(self, batch_id):
            return type("BatchObj", (), {
                "status": "completed",
                "output_file_id": "file_out",
                "error_file_id": None,
            })()

    fake_client = type("FakeGroq", (), {"files": FakeFiles(), "batches": FakeBatches()})()

    monkeypatch.setattr(meal_plan_batch_service, "_get_groq_client", lambda: fake_client)

    fallback_called = []

    def fake_schedule(users, week_start, week_end):
        fallback_called.extend([user.id for user in users])

    monkeypatch.setattr(
        meal_plan_batch_service,
        "_schedule_synchronous_generation",
        fake_schedule,
    )

    monkeypatch.setattr(
        "meals.meal_plan_service.perform_comprehensive_sanity_check",
        lambda meal, user, request_id=None: True,
    )
    monkeypatch.setattr(
        "meals.meal_plan_service.analyze_and_replace_meals",
        lambda user, meal_plan, meal_types, request_id=None: None,
    )
    monkeypatch.setattr(
        meal_plan_batch_service.determine_usage_for_meal,
        "delay",
        lambda *args, **kwargs: None,
    )

    meal_plan_batch_service.process_batch_job(job.id)

    job.refresh_from_db()
    request.refresh_from_db()
    assert job.status == MealPlanBatchJob.STATUS_COMPLETED
    assert request.status == MealPlanBatchRequest.STATUS_COMPLETED
    assert request.response_payload["status_code"] == 200
    assert fallback_called == []

    meal_plan = MealPlan.objects.get(user=user, week_start_date=job.week_start_date)
    assert MealPlanMeal.objects.filter(meal_plan=meal_plan).count() == 1


@pytest.mark.django_db
def test_process_batch_job_failure_triggers_fallback(monkeypatch):
    user = CustomUser.objects.create_user(username="fallback", password="pass", email="fallback@example.com")
    job = MealPlanBatchJob.objects.create(
        week_start_date=date(2025, 9, 29),
        week_end_date=date(2025, 10, 5),
        status=MealPlanBatchJob.STATUS_SUBMITTED,
        batch_id="batch_fail",
        input_file_id="file_in",
    )
    request = MealPlanBatchRequest.objects.create(
        job=job,
        user=user,
        custom_id=f"plan-{user.id}-2025-09-29",
    )

    class FakeBatches:
        def retrieve(self, batch_id):
            return type("BatchObj", (), {
                "status": "failed",
                "errors": [{"message": "something"}],
                "output_file_id": None,
                "error_file_id": "file_err",
            })()

    fake_client = type("FakeGroq", (), {"files": object(), "batches": FakeBatches()})()

    monkeypatch.setattr(meal_plan_batch_service, "_get_groq_client", lambda: fake_client)

    fallback_called = []

    def fake_schedule(users, week_start, week_end):
        fallback_called.extend([user.id for user in users])

    monkeypatch.setattr(
        meal_plan_batch_service,
        "_schedule_synchronous_generation",
        fake_schedule,
    )

    meal_plan_batch_service.process_batch_job(job.id)

    job.refresh_from_db()
    request.refresh_from_db()
    assert job.status == MealPlanBatchJob.STATUS_FAILED
    assert set(fallback_called) == {user.id}
    assert request.status == MealPlanBatchRequest.STATUS_FALLBACK
