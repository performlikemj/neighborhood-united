from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import (
    get_or_create_profile,
    update_streak,
    award_points,
    register_meal_planned,
    get_leaderboard,
    get_unnotified_achievements,
    mark_achievements_as_notified,
    get_weekly_goal_progress,
    check_achievements,
    UNIFIED_EVENT_POINTS
)

from .models import (
    UserProfile,
    Achievement,
    UserAchievement,
    WeeklyGoal,
    PointsTransaction,
    AnalyticsEvent
)

import json


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_gamification_profile(request):
    """API endpoint to get a user's gamification profile."""
    user = request.user
    profile = get_or_create_profile(user)
    
    # Update streak if user visiting
    current_streak = profile.streak_count
    
    # Get weekly goal progress
    weekly_goal = get_weekly_goal_progress(user)
    
    # Get unnotified achievements to display
    new_achievements = get_unnotified_achievements(user)
    achievements_data = [
        {
            'name': ua.achievement.name, 
            'description': ua.achievement.description,
            'icon': ua.achievement.icon,
            'points': ua.achievement.points_reward,
            'date_earned': ua.achieved_at.strftime('%Y-%m-%d')
        } 
        for ua in new_achievements
    ]
    
    # Mark achievements as notified once fetched
    if new_achievements.exists():
        mark_achievements_as_notified(user)
    
    # Run achievement check to ensure we're up to date
    check_achievements(user)
    
    # Get total achievements earned
    achievements_count = UserAchievement.objects.filter(user=user).count()
    
    # Calculate recent points (last 7 days)
    week_ago = timezone.now() - timezone.timedelta(days=7)
    recent_points = PointsTransaction.objects.filter(
        user=user, 
        transaction_type='earned',
        timestamp__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    return Response({
        'points': profile.points,
        'level': profile.level,
        'level_name': profile.level_name,
        'streak_count': current_streak,
        'total_meals_planned': profile.total_meals_planned,
        'achievements_count': achievements_count,
        'recent_points': recent_points,
        'weekly_goal': {
            'progress': weekly_goal['progress'],
            'completed_days': weekly_goal['completed_days'],
            'target_days': weekly_goal['target_days']
        },
        'new_achievements': achievements_data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaderboard(request):
    """API endpoint to get the leaderboard."""
    top_users = get_leaderboard(limit=10)
    
    # Add rank to each user
    for i, user_data in enumerate(top_users):
        user_data['rank'] = i + 1
    
    # Find current user's position
    user = request.user
    profile = get_or_create_profile(user)
    
    # Check if user is in the top 10
    user_in_top = any(u['username'] == user.username for u in top_users)
    
    # If user not in top 10, add their data with ranking
    if not user_in_top:
        # Count users with more points than current user
        higher_ranks = UserProfile.objects.filter(points__gt=profile.points).count()
        user_rank = higher_ranks + 1

        user_data = {
            'username': user.username,
            'points': profile.points,
            'level': profile.level,
            'level_name': profile.level_name,
            'streak': profile.streak_count,
            'rank': user_rank,
            'is_current_user': True
        }
        
        # Add current user data
        top_users.append(user_data)
    else:
        # Mark the current user in the list
        for user_data in top_users:
            if user_data['username'] == user.username:
                user_data['is_current_user'] = True
            else:
                user_data['is_current_user'] = False
    
    return Response({
        'leaderboard': top_users
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def achievements_list(request):
    """API endpoint to list all achievements and user progress."""
    user = request.user
    
    # Run achievement check to ensure we're up to date
    check_achievements(user)
    
    # Get all achievements
    all_achievements = Achievement.objects.all()
    
    # Get the user's earned achievements
    earned_achievements = set(
        UserAchievement.objects.filter(user=user)
        .values_list('achievement_id', flat=True)
    )
    
    # Format the achievements data
    achievements_data = []
    for achievement in all_achievements:
        # Check if user has earned this achievement
        is_earned = achievement.id in earned_achievements
        
        # Get the date earned if available
        earned_date = None
        if is_earned:
            user_achievement = UserAchievement.objects.get(
                user=user, 
                achievement_id=achievement.id
            )
            earned_date = user_achievement.achieved_at.strftime('%Y-%m-%d')
        
        achievements_data.append({
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'icon': achievement.icon,
            'points_reward': achievement.points_reward,
            'is_earned': is_earned,
            'earned_date': earned_date
        })
    
    return Response({
        'achievements': achievements_data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_history(request):
    """API endpoint to get a user's points transaction history."""
    user = request.user
    
    # Get the page parameter (default to 1)
    page = int(request.GET.get('page', 1))
    page_size = 10
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get transactions for this user
    transactions = PointsTransaction.objects.filter(user=user)\
        .order_by('-timestamp')[offset:offset+page_size]
    
    # Format transaction data
    transaction_data = []
    for transaction in transactions:
        transaction_data.append({
            'amount': transaction.amount,
            'type': transaction.transaction_type,
            'source': transaction.source,
            'description': transaction.description,
            'timestamp': transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Get total count for pagination
    total_transactions = PointsTransaction.objects.filter(user=user).count()
    total_pages = (total_transactions + page_size - 1) // page_size
    
    return Response({
        'transactions': transaction_data,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_transactions': total_transactions
        }
    })


# Add a helper endpoint to get updates for the Streamlit UI
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streamlit_data(request):
    """Endpoint to provide data for the Streamlit UI."""
    try:
        user = request.user
        
        try:
            profile = get_or_create_profile(user)
        except Exception as e:
            return Response({'error': f'Failed to get user profile: {str(e)}'}, status=500)
        
        # Get weekly goal
        try:
            weekly_goal = get_weekly_goal_progress(user)
        except Exception as e:
            return Response({'error': f'Failed to get weekly goal progress: {str(e)}'}, status=500)
        
        # Check for new achievements
        try:
            unnotified = get_unnotified_achievements(user)
            has_new_achievements = unnotified.exists()
        except Exception as e:
            return Response({'error': f'Failed to check for new achievements: {str(e)}'}, status=500)
        
        # Format for Streamlit
        try:
            data = {
                'user_level': profile.level_name,
                'meal_plan_streak': profile.streak_count,
                'total_meals_planned': profile.total_meals_planned,
                'points': profile.points,
                'weekly_goal': {
                    'progress': weekly_goal['progress'],
                    'completed_days': weekly_goal['completed_days'],
                    'target_days': weekly_goal['target_days'],
                    'text': f"{weekly_goal['completed_days']}/{weekly_goal['target_days']} days planned"
                },
                'has_new_achievements': has_new_achievements
            }
        except Exception as e:
            return Response({'error': f'Failed to format data: {str(e)}'}, status=500)
        
        return Response(data)
    except Exception as e:
        return Response({'error': f'Unexpected error: {str(e)}'}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def event_handler(request):
    """
    API endpoint to handle gamification events.
    Expects a JSON payload with event details.
    
    Example payload:
    {
        "event_type": "meal_planned",
        "details": {
            "meal_id": 123,
            "timestamp": "2025-03-30T14:34:45Z"
        }
    }
    """
    user = request.user
    try:
        event_data = request.data  # DRF parses JSON automatically
        event_type = event_data.get('event_type')
        details = event_data.get('details', {})

        if not event_type:
            return Response({'error': 'event_type is required'}, status=400)

        # Always record an analytics event with the appropriate score
        event_score = UNIFIED_EVENT_POINTS.get(event_type, 0)
        AnalyticsEvent.objects.create(
            user=user,
            event_type=event_type,
            value=event_score,
            additional_data=details,
        )

        # Handle specific gamification events based on unified point system
        if event_type == 'meal_planned':
            register_meal_planned(user)
        elif event_type == 'login':
            update_streak(user)
        elif event_type in UNIFIED_EVENT_POINTS:
            # Award points for any event in our unified system (except already handled above)
            if event_type not in ['meal_planned', 'login']:
                award_points(user, UNIFIED_EVENT_POINTS[event_type], 'other', event_type)
        else:
            return Response({'error': f'Unsupported event type: {event_type}'}, status=400)

        return Response({'status': 'Event processed successfully', 'event_type': event_type})
    except Exception as e:
        return Response({'error': str(e)}, status=500)