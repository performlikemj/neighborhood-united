"""
QStash webhook handlers for triggering Celery tasks.

QStash sends HTTP POST requests on a schedule, which this endpoint converts
to Celery task calls. This replaces Celery Beat with a serverless scheduler.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_qstash_signature(request):
    """
    Verify the request came from QStash using the official SDK.
    
    Uses the qstash Receiver class for proper JWT verification.
    See: https://upstash.com/docs/qstash/howto/signature
    """
    try:
        from qstash import Receiver
    except ImportError:
        logger.error("qstash package not installed - cannot verify signatures")
        return False
    
    signature = request.headers.get('Upstash-Signature')
    if not signature:
        logger.warning("QStash request missing Upstash-Signature header")
        return False
    
    current_key = getattr(settings, 'QSTASH_CURRENT_SIGNING_KEY', None)
    next_key = getattr(settings, 'QSTASH_NEXT_SIGNING_KEY', None)
    
    if not current_key:
        logger.error("QSTASH_CURRENT_SIGNING_KEY not configured")
        return False
    
    try:
        receiver = Receiver(
            current_signing_key=current_key,
            next_signing_key=next_key or current_key,
        )
        
        # Get the full URL that QStash called
        url = request.build_absolute_uri()
        body = request.body.decode('utf-8') if request.body else ""
        
        # Verify returns True if valid, raises exception if invalid
        receiver.verify(
            signature=signature,
            body=body,
            url=url,
        )
        return True
        
    except Exception as e:
        logger.warning(f"QStash signature verification failed: {e}")
        return False


# Map of URL-safe task names to Celery task paths
TASK_MAP = {
    # Meal/embedding tasks
    "update_embeddings": "meals.meal_embedding.update_embeddings",
    "submit_weekly_meal_plan_batch": "meals.tasks.submit_weekly_meal_plan_batch",
    "poll_incomplete_meal_plan_batches": "meals.tasks.poll_incomplete_meal_plan_batches",
    "cleanup_old_meal_plans_and_meals": "meals.tasks.cleanup_old_meal_plans_and_meals",
    
    # Chef payment tasks
    "sync_all_chef_payments": "meals.tasks.sync_all_chef_payments",
    "process_chef_meal_price_adjustments": "meals.tasks.process_chef_meal_price_adjustments",
    "sync_service_tier_prices": "chef_services.tasks.sync_pending_service_tiers",
    
    # Cleanup tasks
    "cleanup_expired_sessions": "customer_dashboard.tasks.cleanup_expired_sessions",
}


@csrf_exempt
@require_POST
def trigger_task(request, task_name):
    """
    Generic endpoint to trigger any registered Celery task.
    
    QStash calls this endpoint on a schedule. We verify the signature,
    then queue the corresponding Celery task for the worker to execute.
    
    URL: /api/cron/trigger/<task_name>/
    """
    # Verify the request came from QStash
    if not verify_qstash_signature(request):
        logger.warning(f"Unauthorized cron trigger attempt for task: {task_name}")
        return JsonResponse({"error": "Invalid signature"}, status=401)
    
    # Check if task is registered
    if task_name not in TASK_MAP:
        logger.warning(f"Unknown task requested: {task_name}")
        return JsonResponse({"error": "Unknown task"}, status=404)
    
    task_path = TASK_MAP[task_name]
    
    try:
        # Import Celery app and queue the task
        from celery import current_app
        result = current_app.send_task(task_path)
        
        logger.info(f"QStash triggered task {task_name} -> {task_path}, task_id={result.id}")
        
        return JsonResponse({
            "status": "queued",
            "task_name": task_name,
            "task_path": task_path,
            "task_id": str(result.id)
        })
        
    except Exception as e:
        logger.error(f"Failed to queue task {task_name}: {e}")
        return JsonResponse({
            "error": "Failed to queue task",
            "detail": str(e)
        }, status=500)


@csrf_exempt
@require_POST  
def trigger_task_debug(request, task_name):
    """
    Debug endpoint that skips signature verification.
    
    ONLY enable this in development! Remove or disable in production.
    
    URL: /api/cron/trigger-debug/<task_name>/
    """
    if not settings.DEBUG:
        return JsonResponse({"error": "Debug endpoint disabled"}, status=403)
    
    if task_name not in TASK_MAP:
        return JsonResponse({"error": "Unknown task"}, status=404)
    
    task_path = TASK_MAP[task_name]
    
    try:
        from celery import current_app
        result = current_app.send_task(task_path)
        
        logger.info(f"DEBUG triggered task {task_name} -> {task_path}, task_id={result.id}")
        
        return JsonResponse({
            "status": "queued",
            "task_name": task_name,
            "task_path": task_path,
            "task_id": str(result.id)
        })
        
    except Exception as e:
        logger.error(f"Failed to queue task {task_name}: {e}")
        return JsonResponse({
            "error": "Failed to queue task",
            "detail": str(e)
        }, status=500)


def list_tasks(request):
    """
    List all available tasks that can be triggered.
    
    Only available in DEBUG mode to prevent information disclosure.
    
    URL: /api/cron/tasks/
    """
    if not settings.DEBUG:
        return JsonResponse({"error": "Endpoint disabled"}, status=403)
    
    return JsonResponse({
        "tasks": list(TASK_MAP.keys()),
        "count": len(TASK_MAP)
    })

