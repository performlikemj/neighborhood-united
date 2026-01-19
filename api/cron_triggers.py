"""
QStash webhook handlers for executing scheduled tasks.

QStash sends HTTP POST requests on a schedule, which this endpoint
executes synchronously. This eliminates the need for Celery workers
polling Redis continuously.

For long-running tasks, QStash workflows are used to chain execution.
"""
import logging
import traceback
import uuid
from importlib import import_module

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


def execute_task_sync(task_path: str, *args, **kwargs):
    """
    Execute a task function synchronously by importing and calling it directly.
    
    This replaces Celery's send_task() to avoid Redis broker usage.
    
    Args:
        task_path: Dotted path to the task function (e.g., 'meals.tasks.sync_all_chef_payments')
        *args, **kwargs: Arguments to pass to the task function
        
    Returns:
        The result of the task function
    """
    module_path, func_name = task_path.rsplit('.', 1)
    module = import_module(module_path)
    func = getattr(module, func_name)
    
    # Call the function directly (not .delay())
    return func(*args, **kwargs)


# Map of URL-safe task names to task module paths
# Tasks are executed synchronously - no Celery queue involved
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
    Execute a registered task synchronously.
    
    QStash calls this endpoint on a schedule. We verify the signature,
    then execute the task directly (no Celery queue).
    
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
    execution_id = str(uuid.uuid4())[:8]
    
    try:
        logger.info(f"[{execution_id}] QStash executing task {task_name} -> {task_path}")
        
        # Execute the task synchronously
        result = execute_task_sync(task_path)
        
        logger.info(f"[{execution_id}] Task {task_name} completed successfully")
        
        return JsonResponse({
            "status": "completed",
            "task_name": task_name,
            "task_path": task_path,
            "execution_id": execution_id,
            "result": str(result) if result else None
        })
        
    except Exception as e:
        logger.error(f"[{execution_id}] Task {task_name} failed: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            "status": "error",
            "task_name": task_name,
            "execution_id": execution_id,
            "error": str(e),
            "traceback": traceback.format_exc() if settings.DEBUG else None
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
    execution_id = str(uuid.uuid4())[:8]
    
    try:
        logger.info(f"[{execution_id}] DEBUG executing task {task_name} -> {task_path}")
        
        # Execute the task synchronously
        result = execute_task_sync(task_path)
        
        logger.info(f"[{execution_id}] DEBUG task {task_name} completed")
        
        return JsonResponse({
            "status": "completed",
            "task_name": task_name,
            "task_path": task_path,
            "execution_id": execution_id,
            "result": str(result) if result else None
        })
        
    except Exception as e:
        logger.error(f"[{execution_id}] DEBUG task {task_name} failed: {e}")
        return JsonResponse({
            "status": "error",
            "task_name": task_name,
            "execution_id": execution_id,
            "error": str(e),
            "traceback": traceback.format_exc()
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

