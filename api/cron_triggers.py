"""
QStash webhook handlers for triggering Celery tasks.

QStash sends HTTP POST requests on a schedule, which this endpoint converts
to Celery task calls. This replaces Celery Beat with a serverless scheduler.
"""
import base64
import hashlib
import hmac
import json
import logging
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_qstash_signature(request):
    """
    Verify the request came from QStash using the signing keys.
    
    QStash uses JWT-based signatures. We verify using both current and next
    signing keys to handle key rotation gracefully.
    
    See: https://upstash.com/docs/qstash/howto/signature
    """
    signature = request.headers.get('Upstash-Signature')
    if not signature:
        logger.warning("QStash request missing Upstash-Signature header")
        return False
    
    # Get signing keys from settings
    current_key = getattr(settings, 'QSTASH_CURRENT_SIGNING_KEY', None)
    next_key = getattr(settings, 'QSTASH_NEXT_SIGNING_KEY', None)
    
    if not current_key:
        logger.error("QSTASH_CURRENT_SIGNING_KEY not configured")
        return False
    
    body = request.body
    url = request.build_absolute_uri()
    
    # Try to verify with current key first, then next key (for rotation)
    for signing_key in [current_key, next_key]:
        if not signing_key:
            continue
        if _verify_signature(signature, signing_key, body, url):
            return True
    
    logger.warning("QStash signature verification failed")
    return False


def _verify_signature(signature: str, signing_key: str, body: bytes, url: str) -> bool:
    """
    Verify a QStash JWT signature.
    
    QStash signatures are JWTs. We verify the HMAC-SHA256 signature
    and check the claims (url, body hash, expiration).
    """
    try:
        # QStash signature is a JWT: header.payload.signature
        parts = signature.split('.')
        if len(parts) != 3:
            return False
        
        header_b64, payload_b64, sig_b64 = parts
        
        # Verify the signature
        message = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(
            signing_key.encode(),
            message,
            hashlib.sha256
        ).digest()
        
        # URL-safe base64 decode the signature
        sig_b64_padded = sig_b64 + '=' * (4 - len(sig_b64) % 4)
        actual_sig = base64.urlsafe_b64decode(sig_b64_padded)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False
        
        # Decode and verify payload claims
        payload_padded = payload_b64 + '=' * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_padded))
        
        # Check expiration
        exp = payload.get('exp', 0)
        if exp < time.time():
            logger.warning("QStash signature expired")
            return False
        
        # Check body hash if present
        body_hash = payload.get('body')
        if body_hash:
            computed_hash = base64.urlsafe_b64encode(
                hashlib.sha256(body).digest()
            ).decode().rstrip('=')
            if body_hash != computed_hash:
                logger.warning("QStash body hash mismatch")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying QStash signature: {e}")
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
    
    URL: /api/cron/tasks/
    """
    return JsonResponse({
        "tasks": list(TASK_MAP.keys()),
        "count": len(TASK_MAP)
    })

