from django.utils import timezone
from django.conf import settings
from django.db.models import Q
import os
import logging

from celery import shared_task

from .models import Chef, ChefWaitlistSubscription, ChefWaitlistConfig, AreaWaitlist
from meals.email_service import send_system_update_email

logger = logging.getLogger(__name__)


def send_chef_waitlist_notifications(chef_id: int, activation_epoch: int) -> None:
    """Notify subscribers that a chef is active again.

    Uses the assistant email template system for consistent formatting.
    """
    # Feature toggle guard
    if not ChefWaitlistConfig.get_enabled():
        return

    try:
        chef = Chef.objects.select_related('user').get(id=chef_id)
    except Chef.DoesNotExist:
        return

    base_url = os.getenv('STREAMLIT_URL') or ''
    chef_username = getattr(chef.user, 'username', 'chef')
    # Prefer by-username public route
    chef_profile_url = f"{base_url}/chefs/{chef_username}" if base_url else f"/chefs/{chef_username}"

    # Batch fetch subscriptions requiring notification
    qs = (
        ChefWaitlistSubscription.objects
        .select_related('user')
        .filter(
            chef=chef,
            active=True,
        )
        .filter(Q(last_notified_epoch__lt=activation_epoch) | Q(last_notified_epoch__isnull=True))
        .filter(user__email_confirmed=True)
    )

    now = timezone.now()
    subject = f"Chef {chef_username} is now accepting orders"
    message = f"Chef {chef_username} just opened orders. View their profile: {chef_profile_url}"

    user_ids = list(qs.values_list('user_id', flat=True))
    if not user_ids:
        return

    # Send assistant-driven email to all targets
    try:
        send_system_update_email(
            subject,
            message,
            user_ids=user_ids,
            template_key='chef_waitlist_activation',
            template_context={'chef_username': chef_username, 'chef_profile_url': chef_profile_url},
        )
    except Exception:
        # If sending fails, do not update subscriptions, so a later retry can notify
        return

    # Mark as notified for this epoch (after scheduling)
    (
        ChefWaitlistSubscription.objects
        .filter(
            chef=chef,
            active=True,
            user_id__in=user_ids,
        )
        .filter(Q(last_notified_epoch__lt=activation_epoch) | Q(last_notified_epoch__isnull=True))
        .update(last_notified_epoch=activation_epoch, last_notified_at=now)
    )

    return


def notify_waitlist_subscribers_for_chef(chef_id: int) -> None:
    """Simplified: notify all active subscribers that a chef now has open orderable events.

    - Ignores cooldowns/epochs; sends once and deactivates the subscriptions.
    - Uses the same assistant-driven email template for consistency.
    """
    try:
        chef = Chef.objects.select_related('user').get(id=chef_id)
    except Chef.DoesNotExist:
        return

    base_url = os.getenv('STREAMLIT_URL') or ''
    chef_username = getattr(chef.user, 'username', 'chef')
    chef_profile_url = f"{base_url}/chefs/{chef_username}" if base_url else f"/chefs/{chef_username}"

    # Active subscriptions (only confirmed emails)
    qs = (
        ChefWaitlistSubscription.objects
        .select_related('user')
        .filter(chef=chef, active=True, user__email_confirmed=True)
    )

    user_ids = list(qs.values_list('user_id', flat=True))
    if not user_ids:
        return

    subject = f"Chef {chef_username} is now accepting orders"
    message = f"Chef {chef_username} just opened orders. View their profile: {chef_profile_url}"

    try:
        send_system_update_email(
            subject,
            message,
            user_ids=user_ids,
            template_key='chef_waitlist_activation',
            template_context={'chef_username': chef_username, 'chef_profile_url': chef_profile_url},
        )
    except Exception:
        # If sending fails, do not change subscriptions; a later retry may succeed
        return

    now = timezone.now()
    # Deactivate subscriptions after scheduling to avoid duplicate notifications
    ChefWaitlistSubscription.objects.filter(chef=chef, active=True, user_id__in=user_ids).update(
        active=False,
        last_notified_epoch=None,
        last_notified_at=now,
    )

    return


def notify_area_waitlist_users(postal_code: str, country: str, chef_username: str) -> None:
    """Notify users on the area waitlist that a chef is now available in their area.
    
    This is triggered when a verified chef adds a new postal code to their service area.
    
    Args:
        postal_code: Normalized postal code
        country: Country code (e.g., 'US', 'CA')
        chef_username: Username of the chef who joined the area (for the email)
    """
    from shared.services.location_service import LocationService
    
    # Normalize the postal code using LocationService
    normalized = LocationService.normalize(postal_code)
    if not normalized:
        return
    
    # Get users waiting in this area who haven't been notified yet
    waiting_users = AreaWaitlist.get_waiting_users_for_area(normalized, country)
    
    user_ids = list(waiting_users.values_list('user_id', flat=True))
    if not user_ids:
        return
    
    base_url = os.getenv('STREAMLIT_URL') or ''
    chef_profile_url = f"{base_url}/chefs/{chef_username}" if base_url else f"/chefs/{chef_username}"
    discover_url = f"{base_url}/chefs" if base_url else "/chefs"
    
    subject = "A chef is now available in your area!"
    message = (
        f"Great news! Chef {chef_username} is now serving your area. "
        f"Visit their profile to explore their offerings: {chef_profile_url}\n\n"
        f"Or browse all available chefs: {discover_url}"
    )
    
    try:
        send_system_update_email(
            subject,
            message,
            user_ids=user_ids,
            template_key='area_chef_available',
            template_context={
                'chef_username': chef_username,
                'chef_profile_url': chef_profile_url,
                'discover_url': discover_url,
                'postal_code': postal_code,
            },
        )
    except Exception:
        # If sending fails, don't update waitlist - allow retry
        return
    
    now = timezone.now()
    # Mark users as notified using the new FK-based query
    AreaWaitlist.objects.filter(
        location__code=normalized,
        location__country=country,
        notified=False,
        user_id__in=user_ids
    ).update(
        notified=True,
        notified_at=now
    )
    
    return


def _get_groq_client():
    """Lazy Groq client factory - same pattern as meal_generation.py"""
    try:
        from groq import Groq
        import os
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key:
            return Groq(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to create Groq client: {e}")
    return None


def _build_dietary_context(plan) -> str:
    """Build dietary context string from a ChefMealPlan's customer or lead.

    Handles both Customer (M2M relationships) and Lead (ArrayField) data structures.
    Returns a formatted string for inclusion in AI prompts.
    """
    dietary_summary = []

    customer = plan.customer
    lead = plan.lead

    if customer:
        # Customer: M2M relationships for dietary preferences
        dietary_prefs = list(customer.dietary_preferences.values_list('name', flat=True))
        if dietary_prefs:
            dietary_summary.append(f"Dietary preferences: {', '.join(dietary_prefs)}")

        # Custom dietary preferences (M2M)
        custom_prefs = list(customer.custom_dietary_preferences.values_list('name', flat=True))
        if custom_prefs:
            dietary_summary.append(f"Custom dietary preferences: {', '.join(custom_prefs)}")

        # Allergies (ArrayField)
        all_allergies = set((customer.allergies or []) + (customer.custom_allergies or []))
        if all_allergies:
            dietary_summary.append(f"Allergies (MUST AVOID): {', '.join(all_allergies)}")

        # Household members (M2M with dietary_preferences M2M)
        if hasattr(customer, 'household_members'):
            members = customer.household_members.all()
            if members.exists():
                members_desc = []
                for m in members:
                    desc = m.name
                    member_prefs = list(m.dietary_preferences.values_list('name', flat=True))
                    if member_prefs:
                        desc += f" ({', '.join(member_prefs)})"
                    if m.age:
                        desc += f", age {m.age}"
                    # Include allergies for HouseholdMember (mirrors LeadHouseholdMember)
                    member_allergies = set((m.allergies or []) + (m.custom_allergies or []))
                    if member_allergies:
                        desc += f" [allergies: {', '.join(member_allergies)}]"
                    members_desc.append(desc)
                dietary_summary.append(f"Household members: {', '.join(members_desc)}")

    elif lead:
        # Lead: ArrayField for dietary preferences
        if lead.dietary_preferences:
            dietary_summary.append(f"Dietary preferences: {', '.join(lead.dietary_preferences)}")

        # Allergies (ArrayField)
        all_allergies = set((lead.allergies or []) + (lead.custom_allergies or []))
        if all_allergies:
            dietary_summary.append(f"Allergies (MUST AVOID): {', '.join(all_allergies)}")

        # Household members (related LeadHouseholdMember with ArrayFields)
        members = lead.household_members.all()
        if members.exists():
            members_desc = []
            for m in members:
                desc = m.name
                if m.dietary_preferences:
                    desc += f" ({', '.join(m.dietary_preferences)})"
                if m.age:
                    desc += f", age {m.age}"
                # LeadHouseholdMember has allergies field (unlike Customer HouseholdMember)
                member_allergies = set((m.allergies or []) + (m.custom_allergies or []))
                if member_allergies:
                    desc += f" [allergies: {', '.join(member_allergies)}]"
                members_desc.append(desc)
            dietary_summary.append(f"Household members: {', '.join(members_desc)}")

    return '\n'.join(dietary_summary) if dietary_summary else 'No specific dietary requirements.'


def generate_meal_plan_suggestions_async(job_id: int) -> None:
    """Generate AI meal suggestions asynchronously using Groq.
    
    This task runs in the background so chefs don't have to wait.
    Results are stored in the MealPlanGenerationJob model.
    
    Args:
        job_id: ID of the MealPlanGenerationJob to process
    """
    from datetime import timedelta
    import json
    
    from meals.models import MealPlanGenerationJob, ChefMealPlan
    
    print(f"[CELERY TASK] Starting generate_meal_plan_suggestions_async for job_id={job_id}")
    logger.info(f"[CELERY TASK] Starting generate_meal_plan_suggestions_async for job_id={job_id}")
    
    try:
        job = MealPlanGenerationJob.objects.select_related(
            'plan__customer', 'plan__lead', 'chef'
        ).prefetch_related(
            'plan__customer__household_members__dietary_preferences',
            'plan__customer__dietary_preferences',
            'plan__customer__custom_dietary_preferences',
            'plan__lead__household_members',
        ).get(id=job_id)
        print(f"[CELERY TASK] Job {job_id} loaded successfully")
    except MealPlanGenerationJob.DoesNotExist:
        print(f"[CELERY TASK] ERROR: Job {job_id} not found")
        logger.error(f"Generation job {job_id} not found")
        return
    
    # Mark as processing
    print(f"[CELERY TASK] Marking job {job_id} as processing")
    job.mark_processing()
    
    try:
        plan = job.plan

        # Build dietary context from customer OR lead
        dietary_text = _build_dietary_context(plan)
        print(f"[CELERY TASK] Dietary context built: {dietary_text[:100]}...")
        
        # Determine which slots need meals
        slots_to_fill = []
        meal_types = ['breakfast', 'lunch', 'dinner']

        # Build existing items map keyed by date string for precise matching
        existing_items = {}
        for day in plan.days.all():
            date_str = day.date.isoformat()
            for item in day.items.all():
                key = f"{date_str}_{item.meal_type}"
                existing_items[key] = item

        # Calculate date range
        num_days = (plan.end_date - plan.start_date).days + 1

        # Use week_offset to determine which 7-day chunk to generate for
        week_offset = getattr(job, 'week_offset', 0) or 0
        start_offset = week_offset * 7
        end_offset = min(start_offset + 7, num_days)

        if job.mode == 'single_slot':
            # For single slot, find the date from day name in the current week context
            target_day_name = job.target_day
            for i in range(start_offset, end_offset):
                current_date = plan.start_date + timedelta(days=i)
                if current_date.strftime('%A') == target_day_name:
                    slots_to_fill.append({
                        'date': current_date.isoformat(),
                        'day': target_day_name,
                        'meal_type': job.target_meal_type
                    })
                    break
        elif job.mode == 'fill_empty':
            for i in range(start_offset, end_offset):
                current_date = plan.start_date + timedelta(days=i)
                date_str = current_date.isoformat()
                day_name = current_date.strftime('%A')
                for mt in meal_types:
                    key = f"{date_str}_{mt}"
                    if key not in existing_items:
                        slots_to_fill.append({
                            'date': date_str,
                            'day': day_name,
                            'meal_type': mt
                        })
        else:  # full_week
            for i in range(start_offset, end_offset):
                current_date = plan.start_date + timedelta(days=i)
                date_str = current_date.isoformat()
                day_name = current_date.strftime('%A')
                for mt in meal_types:
                    slots_to_fill.append({
                        'date': date_str,
                        'day': day_name,
                        'meal_type': mt
                    })
        
        if not slots_to_fill:
            print(f"[CELERY TASK] No slots to fill, marking complete")
            job.mark_completed([])
            return
        
        # Update slots requested
        job.slots_requested = len(slots_to_fill)
        job.save(update_fields=['slots_requested'])
        print(f"[CELERY TASK] Slots to fill: {len(slots_to_fill)}")
        
        # Generate meals using Groq (faster and uses OSS model)
        print(f"[CELERY TASK] Creating Groq client...")
        client = _get_groq_client()
        if not client:
            raise Exception("Groq client not available - check GROQ_API_KEY")
        print(f"[CELERY TASK] Groq client created successfully")
        
        groq_model = getattr(settings, 'GROQ_MODEL', 'llama-3.1-70b-versatile')

        # Include dates in the slots text for context
        slots_text = '\n'.join([f"- {s['date']} ({s['day']}) {s['meal_type']}" for s in slots_to_fill])

        # Build a lookup map for matching AI response back to our slots
        slot_lookup = {}
        for s in slots_to_fill:
            # Key by day_name + meal_type for matching AI response
            key = f"{s['day'].lower()}_{s['meal_type'].lower()}"
            slot_lookup[key] = s['date']

        system_prompt = f"""You are a professional chef assistant helping create personalized meal plans.

Family dietary context:
{dietary_text}

{f'Chef notes: {job.custom_prompt}' if job.custom_prompt else ''}

Generate appropriate meal suggestions that:
1. Respect ALL allergies (critical - never include allergens)
2. Align with dietary preferences
3. Provide variety across the week
4. Are practical for home preparation
5. Consider the whole household's needs

Respond with a JSON object containing a "suggestions" array."""

        user_prompt = f"""Generate meal suggestions for these slots:
{slots_text}

For each slot, provide:
- date: the date in YYYY-MM-DD format (copy from the slot)
- day: the day name
- meal_type: must be lowercase - one of: breakfast, lunch, dinner, snack
- name: a clear, appetizing meal name
- description: 1-2 sentence description
- dietary_tags: relevant tags like "vegetarian", "gluten-free", etc.
- household_notes: brief note on how this serves the household's needs

Respond ONLY with a valid JSON object containing a "suggestions" array."""

        print(f"[CELERY TASK] Calling Groq API with model {groq_model}...")
        response = client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4000  # Groq is fast, can handle more tokens
        )
        print(f"[CELERY TASK] Groq API response received")
        
        result_text = response.choices[0].message.content
        print(f"[CELERY TASK] Response text: {result_text[:200]}...")
        result_data = json.loads(result_text)
        
        # Handle various response formats - AI might use different keys
        if isinstance(result_data, list):
            suggestions = result_data
        else:
            # Try common keys the AI might use
            suggestions = (
                result_data.get('suggestions') or
                result_data.get('meals') or
                result_data.get('meal_suggestions') or
                result_data.get('menu') or
                []
            )
        print(f"[CELERY TASK] Result keys: {list(result_data.keys()) if isinstance(result_data, dict) else 'array'}")

        # Post-process: ensure each suggestion has a date
        # If AI didn't include it, look it up from our slot_lookup map
        for suggestion in suggestions:
            if not suggestion.get('date'):
                day_name = suggestion.get('day', '')
                meal_type = suggestion.get('meal_type', '')
                lookup_key = f"{day_name.lower()}_{meal_type.lower()}"
                if lookup_key in slot_lookup:
                    suggestion['date'] = slot_lookup[lookup_key]

        print(f"[CELERY TASK] Parsed {len(suggestions)} suggestions, marking complete")
        job.mark_completed(suggestions)
        print(f"[CELERY TASK] Job {job_id} marked complete")
        logger.info(f"Generation job {job_id} completed with {len(suggestions)} suggestions")
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[CELERY TASK] ERROR in job {job_id}: {e}")
        print(f"[CELERY TASK] Traceback: {error_traceback}")
        logger.error(f"Generation job {job_id} failed: {e}\n{error_traceback}")
        job.mark_failed(str(e))
        
        # Retry on certain failures
        if self.request.retries < self.max_retries:
            print(f"[CELERY TASK] Retrying task (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)


# ═══════════════════════════════════════════════════════════════════════════════
# PROACTIVE INSIGHTS GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_chef_proactive_insights(self, chef_id: int = None):
    """
    Generate proactive insights for chefs.
    
    Run daily for all chefs, or on-demand for a specific chef.
    Uses the service module for insight generation logic.
    
    Args:
        chef_id: If provided, generate for this chef only. Otherwise, all active chefs.
    """
    from chefs.services.proactive_insights import (
        generate_chef_insights,
        save_insights,
        expire_old_insights
    )
    
    try:
        # Get chefs to process
        if chef_id:
            chefs = Chef.objects.filter(id=chef_id, user__is_active=True)
        else:
            chefs = Chef.objects.filter(user__is_active=True)
        
        total_insights = 0
        chefs_processed = 0
        
        for chef in chefs:
            try:
                # Expire old insights first
                expired = expire_old_insights(chef)
                if expired > 0:
                    logger.info(f"Expired {expired} old insights for chef {chef.id}")
                
                # Generate new insights
                insights = generate_chef_insights(chef)
                created = save_insights(insights)
                
                total_insights += created
                chefs_processed += 1
                
                if created > 0:
                    logger.info(f"Generated {created} insights for chef {chef.id}")
                    
            except Exception as e:
                logger.error(f"Failed to generate insights for chef {chef.id}: {e}")
                continue
        
        return {
            'status': 'success',
            'chefs_processed': chefs_processed,
            'insights_created': total_insights
        }
        
    except Exception as e:
        logger.error(f"Error in generate_chef_proactive_insights: {e}")
        raise self.retry(exc=e)


@shared_task
def generate_daily_chef_insights():
    """
    Daily task to generate proactive insights for all active chefs.
    
    Schedule this in celerybeat to run daily (e.g., 6 AM).
    """
    return generate_chef_proactive_insights.delay(chef_id=None)
