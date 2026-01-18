"""
API endpoints for chef's meal plan management.

These endpoints allow chefs to create, update, and manage
meal plans for their clients, and respond to client suggestions.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef
from chef_services.models import ChefCustomerConnection
from meals.models import (
    ChefMealPlan,
    ChefMealPlanDay,
    ChefMealPlanItem,
    MealPlanSuggestion
)


def get_chef_for_request(request):
    """Get the Chef object for the current user."""
    if not hasattr(request.user, 'chef'):
        return None
    return request.user.chef


def _serialize_suggestion(s):
    """Serialize a MealPlanSuggestion for API response."""
    return {
        'id': s.id,
        'customer': {
            'id': s.customer.id,
            'username': s.customer.username,
            'display_name': f"{s.customer.first_name} {s.customer.last_name}".strip() or s.customer.username,
        },
        'suggestion_type': s.suggestion_type,
        'suggestion_type_display': s.get_suggestion_type_display(),
        'description': s.description,
        'status': s.status,
        'status_display': s.get_status_display(),
        'chef_response': s.chef_response,
        'target_item': {
            'id': s.target_item.id,
            'name': s.target_item.display_name,
            'meal_type': s.target_item.meal_type,
        } if s.target_item else None,
        'target_day': {
            'id': s.target_day.id,
            'date': s.target_day.date.isoformat(),
        } if s.target_day else None,
        'created_at': s.created_at.isoformat(),
        'reviewed_at': s.reviewed_at.isoformat() if s.reviewed_at else None,
    }


def _serialize_plan_for_chef(plan, include_days=False):
    """Serialize a ChefMealPlan for chef API response."""
    result = {
        'id': plan.id,
        'title': plan.title or f"Plan for {plan.start_date}",
        'start_date': plan.start_date.isoformat(),
        'end_date': plan.end_date.isoformat(),
        'status': plan.status,
        'notes': plan.notes,
        'published_at': plan.published_at.isoformat() if plan.published_at else None,
        'created_at': plan.created_at.isoformat(),
        'updated_at': plan.updated_at.isoformat(),
        'pending_suggestions': plan.pending_suggestions_count,
        'customer': {
            'id': plan.customer.id,
            'username': plan.customer.username,
            'display_name': f"{plan.customer.first_name} {plan.customer.last_name}".strip() or plan.customer.username,
        }
    }
    
    if include_days:
        days = []
        for day in plan.days.prefetch_related('items__meal').all():
            day_data = {
                'id': day.id,
                'date': day.date.isoformat(),
                'is_skipped': day.is_skipped,
                'skip_reason': day.skip_reason,
                'notes': day.notes,
                'items': []
            }
            for item in day.items.all():
                day_data['items'].append({
                    'id': item.id,
                    'meal_type': item.meal_type,
                    'name': item.display_name,
                    'description': item.display_description,
                    'servings': item.servings,
                    'notes': item.notes,
                    'meal_id': item.meal_id,
                })
            days.append(day_data)
        result['days'] = days
    
    return result


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_plans(request, client_id):
    """
    GET: List meal plans for a specific client
    POST: Create a new meal plan for a client
    """
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Verify connection with client
    connection = get_object_or_404(
        ChefCustomerConnection,
        chef=chef,
        customer_id=client_id,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    )
    
    if request.method == 'GET':
        status_filter = request.query_params.get('status')
        
        plans = ChefMealPlan.objects.filter(
            chef=chef,
            customer_id=client_id
        ).order_by('-start_date')
        
        if status_filter:
            plans = plans.filter(status=status_filter)
        
        return Response({
            'plans': [_serialize_plan_for_chef(plan) for plan in plans],
            'count': plans.count()
        })
    
    elif request.method == 'POST':
        title = request.data.get('title', '')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        notes = request.data.get('notes', '')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if start_date > end_date:
            return Response(
                {'error': 'start_date must be before end_date.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for duplicate plan
        existing = ChefMealPlan.objects.filter(
            chef=chef,
            customer_id=client_id,
            start_date=start_date
        ).exists()
        
        if existing:
            return Response(
                {'error': 'A plan already exists for this client starting on this date.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        plan = ChefMealPlan.objects.create(
            chef=chef,
            customer_id=client_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
            status=ChefMealPlan.STATUS_DRAFT
        )
        
        return Response(
            _serialize_plan_for_chef(plan),
            status=status.HTTP_201_CREATED
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def plan_detail(request, plan_id):
    """
    GET: Get plan details
    PUT: Update plan
    DELETE: Delete plan (only drafts)
    """
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(
        ChefMealPlan.objects.select_related('customer'),
        id=plan_id,
        chef=chef
    )
    
    if request.method == 'GET':
        return Response(_serialize_plan_for_chef(plan, include_days=True))
    
    elif request.method == 'PUT':
        from datetime import datetime

        title = request.data.get('title', plan.title)
        notes = request.data.get('notes', plan.notes)
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')

        # Check if date changes are being requested
        date_change_requested = start_date_str or end_date_str

        # Return explicit error for non-draft plans trying to change dates
        if date_change_requested and plan.status != ChefMealPlan.STATUS_DRAFT:
            return Response(
                {'error': 'Dates can only be changed for draft plans.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse and validate dates if provided
        new_start_date = plan.start_date
        new_end_date = plan.end_date

        if start_date_str:
            try:
                new_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid start_date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end_date_str:
            try:
                new_end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid end_date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate date range
        if new_start_date > new_end_date:
            return Response(
                {'error': 'Start date must be before or equal to end date.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If dates are changing on a draft plan, perform additional checks
        if date_change_requested and plan.status == ChefMealPlan.STATUS_DRAFT:
            # Check for orphaned meals (days with items outside new date range)
            orphaned_days = ChefMealPlanDay.objects.filter(plan=plan).exclude(
                date__gte=new_start_date,
                date__lte=new_end_date
            )
            orphaned_count = orphaned_days.count()

            if orphaned_count > 0:
                return Response(
                    {'error': f'Cannot change dates: {orphaned_count} meal day(s) would be outside the new range. Delete or reschedule them first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check unique constraint (same chef, customer, start_date)
            if start_date_str:
                duplicate_plan = ChefMealPlan.objects.filter(
                    chef=chef,
                    customer=plan.customer,
                    start_date=new_start_date
                ).exclude(id=plan.id).exists()

                if duplicate_plan:
                    return Response(
                        {'error': 'A plan for this client already starts on this date.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply date changes
            plan.start_date = new_start_date
            plan.end_date = new_end_date

        plan.title = title
        plan.notes = notes
        plan.save()

        return Response(_serialize_plan_for_chef(plan, include_days=True))
    
    elif request.method == 'DELETE':
        if plan.status != ChefMealPlan.STATUS_DRAFT:
            return Response(
                {'error': 'Only draft plans can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        plan.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publish_plan(request, plan_id):
    """Publish a meal plan to make it visible to the customer."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    
    if plan.status == ChefMealPlan.STATUS_PUBLISHED:
        return Response(
            {'error': 'Plan is already published.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if plan.status == ChefMealPlan.STATUS_ARCHIVED:
        return Response(
            {'error': 'Cannot publish an archived plan.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    plan.publish()
    
    return Response({
        'success': True,
        'plan': _serialize_plan_for_chef(plan, include_days=True)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_plan(request, plan_id):
    """Archive a meal plan."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    
    if plan.status == ChefMealPlan.STATUS_ARCHIVED:
        return Response(
            {'error': 'Plan is already archived.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    plan.archive()
    
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_plan_day(request, plan_id):
    """Add a day to a meal plan."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    
    date_str = request.data.get('date')
    is_skipped = request.data.get('is_skipped', False)
    skip_reason = request.data.get('skip_reason', '')
    notes = request.data.get('notes', '')
    
    if not date_str:
        return Response(
            {'error': 'date is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    from datetime import datetime
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if date is within plan range
    if date < plan.start_date or date > plan.end_date:
        return Response(
            {'error': 'Date must be within the plan date range.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for duplicate
    if ChefMealPlanDay.objects.filter(plan=plan, date=date).exists():
        return Response(
            {'error': 'A day already exists for this date.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    day = ChefMealPlanDay.objects.create(
        plan=plan,
        date=date,
        is_skipped=is_skipped,
        skip_reason=skip_reason,
        notes=notes
    )
    
    return Response({
        'id': day.id,
        'date': day.date.isoformat(),
        'is_skipped': day.is_skipped,
        'skip_reason': day.skip_reason,
        'notes': day.notes,
        'items': []
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def plan_day_detail(request, plan_id, day_id):
    """Update or delete a plan day."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    day = get_object_or_404(
        ChefMealPlanDay,
        id=day_id,
        plan_id=plan_id,
        plan__chef=chef
    )
    
    if request.method == 'PUT':
        day.is_skipped = request.data.get('is_skipped', day.is_skipped)
        day.skip_reason = request.data.get('skip_reason', day.skip_reason)
        day.notes = request.data.get('notes', day.notes)
        day.save()
        
        return Response({
            'id': day.id,
            'date': day.date.isoformat(),
            'is_skipped': day.is_skipped,
            'skip_reason': day.skip_reason,
            'notes': day.notes,
        })
    
    elif request.method == 'DELETE':
        day.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_plan_item(request, plan_id, day_id):
    """Add a meal item to a plan day."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    day = get_object_or_404(
        ChefMealPlanDay,
        id=day_id,
        plan_id=plan_id,
        plan__chef=chef
    )
    
    meal_type = request.data.get('meal_type')
    meal_id = request.data.get('meal_id')
    custom_name = request.data.get('custom_name', '')
    custom_description = request.data.get('custom_description', '')
    servings = request.data.get('servings', 1)
    notes = request.data.get('notes', '')
    
    if not meal_type:
        return Response(
            {'error': 'meal_type is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    valid_types = [choice[0] for choice in ChefMealPlanItem.MEAL_TYPE_CHOICES]
    if meal_type not in valid_types:
        return Response(
            {'error': f'Invalid meal_type. Must be one of: {", ".join(valid_types)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not meal_id and not custom_name:
        return Response(
            {'error': 'Either meal_id or custom_name is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify meal belongs to this chef if provided
    meal = None
    if meal_id:
        from meals.models import Meal
        meal = get_object_or_404(Meal, id=meal_id, chef=chef)
    
    item = ChefMealPlanItem.objects.create(
        day=day,
        meal_type=meal_type,
        meal=meal,
        custom_name=custom_name,
        custom_description=custom_description,
        servings=servings,
        notes=notes
    )
    
    return Response({
        'id': item.id,
        'meal_type': item.meal_type,
        'name': item.display_name,
        'description': item.display_description,
        'servings': item.servings,
        'notes': item.notes,
        'meal_id': item.meal_id,
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def plan_item_detail(request, plan_id, day_id, item_id):
    """Update or delete a plan item."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    item = get_object_or_404(
        ChefMealPlanItem,
        id=item_id,
        day_id=day_id,
        day__plan_id=plan_id,
        day__plan__chef=chef
    )
    
    if request.method == 'PUT':
        meal_id = request.data.get('meal_id')
        
        if meal_id:
            from meals.models import Meal
            item.meal = get_object_or_404(Meal, id=meal_id, chef=chef)
            item.custom_name = ''
            item.custom_description = ''
        else:
            item.meal = None
            item.custom_name = request.data.get('custom_name', item.custom_name)
            item.custom_description = request.data.get('custom_description', item.custom_description)
        
        item.servings = request.data.get('servings', item.servings)
        item.notes = request.data.get('notes', item.notes)
        item.save()
        
        return Response({
            'id': item.id,
            'meal_type': item.meal_type,
            'name': item.display_name,
            'description': item.display_description,
            'servings': item.servings,
            'notes': item.notes,
            'meal_id': item.meal_id,
        })
    
    elif request.method == 'DELETE':
        item.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def plan_suggestions(request, plan_id):
    """Get all customer suggestions for a plan."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    
    status_filter = request.query_params.get('status')
    
    suggestions = plan.suggestions.select_related(
        'customer', 'target_item', 'target_day'
    ).order_by('-created_at')
    
    if status_filter:
        suggestions = suggestions.filter(status=status_filter)
    
    return Response({
        'suggestions': [_serialize_suggestion(s) for s in suggestions],
        'count': suggestions.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_suggestion(request, suggestion_id):
    """Respond to a customer suggestion (approve, reject, or modify)."""
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    suggestion = get_object_or_404(
        MealPlanSuggestion.objects.select_related('plan'),
        id=suggestion_id,
        plan__chef=chef
    )
    
    if suggestion.status != MealPlanSuggestion.STATUS_PENDING:
        return Response(
            {'error': 'This suggestion has already been reviewed.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    action = request.data.get('action')  # 'approve', 'reject', 'modify'
    response_text = request.data.get('response', '')
    
    if action not in ['approve', 'reject', 'modify']:
        return Response(
            {'error': 'action must be one of: approve, reject, modify'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action == 'reject' and not response_text:
        return Response(
            {'error': 'A response is required when rejecting a suggestion.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action == 'approve':
        suggestion.approve(response_text)
    elif action == 'reject':
        suggestion.reject(response_text)
    elif action == 'modify':
        suggestion.approve_with_modifications(response_text)
    
    return Response(_serialize_suggestion(suggestion))


# ============================================================================
# AI Meal Generation (Async)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_meals_for_plan(request, plan_id):
    """
    Start async AI meal generation for a plan.
    
    Returns immediately with a job_id. Frontend should poll the job status.
    
    Request body:
    {
        "mode": "full_week" | "fill_empty" | "single_slot",
        "day": "Monday",  // required for single_slot
        "meal_type": "Dinner",  // required for single_slot
        "prompt": "optional custom preferences"
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from meals.models import MealPlanGenerationJob
    from chefs.tasks import generate_meal_plan_suggestions_async
    
    logger.debug(f"generate_meals_for_plan called - plan_id={plan_id}")
    
    chef = get_chef_for_request(request)
    if not chef:
        logger.debug("No chef found for request")
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    logger.debug(f"Chef found: {chef.id}")
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    logger.debug(f"Plan found: {plan.id}, customer={plan.customer_id}")
    
    mode = request.data.get('mode', 'full_week')
    target_day = request.data.get('day', '')
    target_meal_type = request.data.get('meal_type', '')
    custom_prompt = request.data.get('prompt', '')
    week_offset = request.data.get('week_offset', 0)

    # Validate week_offset is a non-negative integer
    try:
        week_offset = int(week_offset)
        if week_offset < 0:
            week_offset = 0
    except (TypeError, ValueError):
        week_offset = 0

    logger.debug(f"Request params: mode={mode}, day={target_day}, meal_type={target_meal_type}, week_offset={week_offset}")
    
    if mode == 'single_slot':
        if not target_day or not target_meal_type:
            logger.debug("Missing day/meal_type for single_slot mode")
            return Response(
                {'error': 'day and meal_type are required for single_slot mode.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Check if there's already a pending/processing job for this plan
    existing_job = MealPlanGenerationJob.objects.filter(
        plan=plan,
        status__in=['pending', 'processing']
    ).first()
    
    if existing_job:
        logger.debug(f"Found existing job: {existing_job.id}, status={existing_job.status}")
        return Response({
            'job_id': existing_job.id,
            'status': existing_job.status,
            'message': 'A generation job is already in progress for this plan.'
        })
    
    # Create the job
    logger.debug("Creating new job...")
    job = MealPlanGenerationJob.objects.create(
        plan=plan,
        chef=chef,
        mode=mode,
        target_day=target_day,
        target_meal_type=target_meal_type,
        custom_prompt=custom_prompt,
        week_offset=week_offset
    )
    logger.debug(f"Job created: {job.id}")
    
    # Queue the async task
    logger.debug(f"Running task for job {job.id}...")
    try:
        generate_meal_plan_suggestions_async(job.id)
        logger.debug(f"Task completed for job {job.id}")
    except Exception as e:
        logger.error(f"Failed to queue task for job {job.id}: {e}")
        job.mark_failed(f"Failed to queue task: {e}")
        return Response({
            'error': f'Failed to queue task: {e}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'job_id': job.id,
        'status': 'pending',
        'message': 'Generation started. Check back for results.'
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_generation_job_status(request, job_id):
    """
    Check the status of an AI meal generation job.
    
    Returns:
    - status: pending | processing | completed | failed
    - suggestions: (only if completed) array of meal suggestions
    - error_message: (only if failed) error description
    """
    from meals.models import MealPlanGenerationJob
    
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    job = get_object_or_404(MealPlanGenerationJob, id=job_id, chef=chef)
    
    response_data = {
        'job_id': job.id,
        'status': job.status,
        'mode': job.mode,
        'slots_requested': job.slots_requested,
        'slots_generated': job.slots_generated,
        'created_at': job.created_at.isoformat(),
    }
    
    if job.status == 'completed':
        response_data['suggestions'] = job.suggestions
        response_data['completed_at'] = job.completed_at.isoformat() if job.completed_at else None
    elif job.status == 'failed':
        response_data['error_message'] = job.error_message
    elif job.status == 'processing':
        response_data['started_at'] = job.started_at.isoformat() if job.started_at else None
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_generation_jobs(request, plan_id):
    """
    List all generation jobs for a plan.
    """
    from meals.models import MealPlanGenerationJob
    
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    plan = get_object_or_404(ChefMealPlan, id=plan_id, chef=chef)
    
    jobs = MealPlanGenerationJob.objects.filter(plan=plan).order_by('-created_at')[:10]
    
    return Response({
        'jobs': [
            {
                'job_id': job.id,
                'status': job.status,
                'mode': job.mode,
                'slots_requested': job.slots_requested,
                'slots_generated': job.slots_generated,
                'created_at': job.created_at.isoformat(),
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            }
            for job in jobs
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chef_dishes(request):
    """
    Get chef's saved meals for quick-add to plans.
    
    Query params:
    - meal_type: filter by meal type (accepts both 'breakfast' and 'Breakfast' formats)
    - search: search by name
    - limit: max results (default 50)
    - composed_only: if 'true', only return meals with 2+ dishes (composed meals)
    - include_dishes: if 'true', include dish details in response
    """
    from meals.models import Meal
    
    chef = get_chef_for_request(request)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    meals = Meal.objects.filter(chef=chef).prefetch_related('dishes').order_by('-created_date')
    
    meal_type = request.query_params.get('meal_type')
    search = request.query_params.get('search')
    limit = int(request.query_params.get('limit', 50))
    composed_only = request.query_params.get('composed_only', '').lower() == 'true'
    include_dishes = request.query_params.get('include_dishes', '').lower() == 'true'
    
    if meal_type:
        # Handle both lowercase (from frontend) and capitalized (in Meal model)
        meals = meals.filter(meal_type__iexact=meal_type)
    
    if search:
        meals = meals.filter(name__icontains=search)
    
    # Filter for composed meals (meals with multiple dishes)
    if composed_only:
        from django.db.models import Count
        meals = meals.annotate(dish_count=Count('dishes')).filter(dish_count__gte=2)
    
    meals = meals[:limit]
    
    results = []
    for meal in meals:
        dietary_prefs = list(meal.dietary_preferences.values_list('name', flat=True))
        meal_data = {
            'id': meal.id,
            'name': meal.name,
            'description': meal.description[:200] if meal.description else '',
            'meal_type': meal.meal_type,
            'dietary_preferences': dietary_prefs,
            'image_url': meal.image.url if meal.image else None,
            'dish_count': meal.dishes.count(),
            'is_composed': meal.dishes.count() >= 2,
        }
        
        # Include dish breakdown if requested
        if include_dishes:
            meal_data['dishes'] = [
                {
                    'id': d.id,
                    'name': d.name,
                }
                for d in meal.dishes.all()
            ]
        
        results.append(meal_data)
    
    return Response({
        'dishes': results,  # Keep key as 'dishes' for backwards compatibility
        'count': len(results)
    })

