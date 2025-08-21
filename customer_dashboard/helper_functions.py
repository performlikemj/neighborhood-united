from datetime import datetime, timedelta

def get_current_week():
    from django.utils import timezone
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)
    return start_week, end_week