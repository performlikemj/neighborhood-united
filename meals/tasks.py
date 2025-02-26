# Constants
MIN_SIMILARITY = 0.6  # Adjusted similarity threshold
MAX_ATTEMPTS = 5      # Max attempts to find or generate a meal per meal type per day
EXPECTED_EMBEDDING_SIZE = 1536  # Example size, adjust based on your embedding model

from celery import shared_task
from .models import SystemUpdate
from .email_service import send_system_update_email

@shared_task
def queue_system_update_email(system_update_id, test_mode=False, admin_id=None):
    """
    Queue system update emails through Celery
    """
    print(f"Queueing system update email for {system_update_id}")
    try:
        system_update = SystemUpdate.objects.get(id=system_update_id)
        
        if test_mode and admin_id:
            # Send test email only to admin
            send_system_update_email.delay(
                subject=system_update.subject,
                message=system_update.message,
                user_ids=[admin_id]
            )
        else:
            # Send to all users
            send_system_update_email.delay(
                subject=system_update.subject,
                message=system_update.message
            )
            print(f"System update email queued for all users!")
        return True
    except SystemUpdate.DoesNotExist:
        return False





















