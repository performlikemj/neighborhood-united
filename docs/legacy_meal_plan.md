# Legacy Meal Plan Stack

The legacy meal-planning surface is still available for compatibility, but it is isolated
behind the `LEGACY_MEAL_PLAN_ENABLED` Django setting. When the flag is disabled the
URLconf omits the endpoints entirely, the feature-flag helpers refuse to send emails, and
all supporting modules expose a `LEGACY_MEAL_PLAN = True` marker so callers can avoid
loading them from new entry points.

## API views

* `meals/views.py` contains all legacy REST and SSE entry points for meal-plan CRUD,
  streaming, cooking-instruction generation, and Instacart link management (for example
  `api_generate_meal_plan`, `api_stream_meal_plan_detail`, and the Instacart helpers).
  These views depend on the serializers listed below plus helpers from
  `meals/meal_plan_service.py`, `meals/meal_instructions.py`, and `meals/instacart_service.py`.
* Server Sent Event endpoints such as `api_stream_meal_plan_generation` rely on Redis pubsub
  locks and emit incremental plan progress to Streamlit clients.
* Instacart URLs are served exclusively from the legacy views – they wrap
  `meals.instacart_service.generate_instacart_link` and are therefore disabled whenever
  `LEGACY_MEAL_PLAN_ENABLED` is false.

## Serializers and helpers

* `meals/serializers.py` exposes `MealPlanMealSerializer`, `MealPlanSerializer`, and
  `MealPlanSummarySerializer`, all of which fuel the JSON payloads returned by the endpoints.
* `meals/meal_plan_service.py` provides the heavy lifting for `create_meal_plan_for_user`,
  `modify_existing_meal_plan`, and `apply_modifications`. These helpers orchestrate Groq/OpenAI
  calls, meal swapping, and sanity checks that the views invoke synchronously.
* `meals/meal_planning_tools.py` adapts the same helpers into OpenAI tool definitions used by the
  assistant. Even though these functions present a tool-facing API (`create_meal_plan`,
  `modify_meal_plan`, `generate_instacart_link_tool`, etc.), they still mutate the same MealPlan
  tables as the REST endpoints and should be considered part of the legacy stack.
* `meals/meal_instructions.py` includes `generate_instructions` and
  `generate_bulk_prep_instructions` Celery tasks, both triggered from the approval and
  notification flow in the legacy views.
* `meals/services/meal_plan_batching.py` plus the Celery tasks in `meals/tasks.py`
  (`submit_weekly_meal_plan_batch`, `poll_incomplete_meal_plan_batches`, and
  `cleanup_old_meal_plans_and_meals`) run the background batch generation jobs referenced by the
  `/api/meal_plan_status/` and streaming endpoints.

## Instacart integration

* `meals/instacart_service.py` contains the Instacart payload builders (`normalize_lines`,
  `create_instacart_shopping_list`, and `generate_instacart_link`). These helpers are only used by
  the legacy meal-plan APIs and the assistant tools noted above; disabling the flag prevents any
  Instacart URL creation while keeping the code path intact.

## Customer health modules

* `customer_dashboard/models.py` defines `UserHealthMetrics`, a per-day snapshot of biometrics that
  the assistant references when fine-tuning meal plans.
* `customer_dashboard/serializers.py` exposes `UserHealthMetricsSerializer` so the health data can
  be displayed inside the dashboard UI and surfaced in reminders.
* `customer_dashboard/views.py` routes `/api/user-metrics`, `/api/user_goal_view`, and
  `/api_goal_management`. These endpoints request updated metrics from users and feed them into the
  same conversation context used by the legacy meal-plan tools, which is why they are documented
  alongside the rest of the stack.

## Operational guidance

* Toggle `LEGACY_MEAL_PLAN_ENABLED` to disable the URLs, Celery tasks, and Instacart feature without
  deleting code. All affected modules expose `LEGACY_MEAL_PLAN = True` so analytics tooling can
  detect when the legacy stack is imported.
* When the flag is off the views are unregistered, the feature flag helper short-circuits email
  sends, and the assistant tools should also be considered unavailable because they all depend on
  these modules. The `/meals/api/config/` endpoint and template context processors expose the flag
  value so frontends can hide `/meal-plans` widgets rather than linking to disabled routes.
