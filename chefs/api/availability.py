"""
Chef Availability API endpoints.

Provides endpoints to check if chefs serve a user's area and manage area waitlists.
Uses LocationService as the single source of truth for postal code operations.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from chefs.models import AreaWaitlist
from shared.services.location_service import LocationService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_chef_availability(request):
    """Check if any verified chefs serve the user's postal code.
    
    Returns:
        {
            'has_chef': bool,
            'postal_code': str | None,
            'country': str | None,
            'reason': str | None,  # Only present if has_chef is False
            'on_waitlist': bool,   # Whether user is on area waitlist
            'waitlist_position': int | None  # Position if on waitlist
        }
    """
    # Use LocationService for comprehensive check
    access_info = LocationService.user_can_access_chef_features(request.user)
    location = access_info['location']
    
    # Check if user has address with postal code
    if not location.normalized_postal and not location.country:
        return Response({
            'has_chef': False,
            'reason': 'no_address',
            'postal_code': None,
            'country': None,
            'on_waitlist': False,
            'waitlist_position': None
        })
    
    if not location.normalized_postal:
        return Response({
            'has_chef': False,
            'reason': 'no_postal_code',
            'postal_code': None,
            'country': location.country,
            'on_waitlist': False,
            'waitlist_position': None
        })
    
    if not location.country:
        return Response({
            'has_chef': False,
            'reason': 'no_country',
            'postal_code': location.display_postal,
            'country': None,
            'on_waitlist': False,
            'waitlist_position': None
        })
    
    has_chef = access_info['has_access']
    
    # Check waitlist status using the new FK-based query
    on_waitlist = AreaWaitlist.objects.filter(
        user=request.user,
        location__code=location.normalized_postal,
        location__country=location.country,
        notified=False
    ).exists()
    
    waitlist_position = None
    if on_waitlist:
        waitlist_position = AreaWaitlist.get_position(
            request.user,
            location.normalized_postal,
            location.country
        )
    
    response_data = {
        'has_chef': has_chef,
        'postal_code': location.display_postal,
        'country': location.country,
        'on_waitlist': on_waitlist,
        'waitlist_position': waitlist_position
    }
    
    if not has_chef:
        response_data['reason'] = access_info.get('reason', 'no_chefs_in_area')
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_area_chef_availability(request):
    """Check if any verified chefs serve a specific postal code (public endpoint).
    
    Query params:
        postal_code: str - The postal code to check
        country: str - The country code (e.g., 'US', 'CA')
    
    Returns:
        {
            'has_chef': bool,
            'postal_code': str,
            'country': str,
            'chef_count': int  # Number of verified chefs in area
        }
    """
    postal_code = request.query_params.get('postal_code', '').strip()
    country = request.query_params.get('country', '').strip()
    
    if not postal_code or not country:
        return Response({
            'error': 'postal_code and country are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    chef_count = LocationService.get_verified_chef_count(postal_code, country)
    
    return Response({
        'has_chef': chef_count > 0,
        'postal_code': postal_code,
        'country': country,
        'chef_count': chef_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_area_waitlist(request):
    """Join the waitlist to be notified when a chef becomes available in user's area.
    
    Returns:
        {
            'success': bool,
            'on_waitlist': bool,
            'position': int,
            'total_waiting': int,
            'postal_code': str,
            'country': str
        }
    """
    location = LocationService.get_user_location(request.user)
    
    if not location.is_complete:
        return Response({
            'success': False,
            'error': 'Please add your postal code and country to your profile first.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if there's already a chef - no need for waitlist
    if LocationService.has_chef_coverage_for_area(location.normalized_postal, location.country):
        return Response({
            'success': False,
            'error': 'Chefs are already available in your area!',
            'has_chef': True
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Use the new join_waitlist method on AreaWaitlist
    entry, created = AreaWaitlist.join_waitlist(
        request.user,
        location.normalized_postal,
        location.country
    )
    
    if not entry:
        return Response({
            'success': False,
            'error': 'Could not join waitlist. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    position = AreaWaitlist.get_position(
        request.user,
        location.normalized_postal,
        location.country
    )
    total_waiting = AreaWaitlist.get_total_waiting(
        location.normalized_postal,
        location.country
    )
    
    return Response({
        'success': True,
        'on_waitlist': True,
        'position': position,
        'total_waiting': total_waiting,
        'postal_code': location.display_postal,
        'country': location.country
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def leave_area_waitlist(request):
    """Remove user from area waitlist.
    
    Returns:
        {
            'success': bool,
            'on_waitlist': bool
        }
    """
    location = LocationService.get_user_location(request.user)
    
    if not location.is_complete:
        return Response({
            'success': True,
            'on_waitlist': False
        })
    
    deleted, _ = AreaWaitlist.objects.filter(
        user=request.user,
        location__code=location.normalized_postal,
        location__country=location.country
    ).delete()
    
    return Response({
        'success': True,
        'on_waitlist': False,
        'removed': deleted > 0
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def area_waitlist_status(request):
    """Get user's waitlist status and position.
    
    Returns:
        {
            'on_waitlist': bool,
            'position': int | None,
            'total_waiting': int,
            'postal_code': str | None,
            'country': str | None
        }
    """
    location = LocationService.get_user_location(request.user)
    
    if not location.is_complete:
        return Response({
            'on_waitlist': False,
            'position': None,
            'total_waiting': 0,
            'postal_code': None,
            'country': None
        })
    
    on_waitlist = AreaWaitlist.objects.filter(
        user=request.user,
        location__code=location.normalized_postal,
        location__country=location.country,
        notified=False
    ).exists()
    
    position = None
    if on_waitlist:
        position = AreaWaitlist.get_position(
            request.user,
            location.normalized_postal,
            location.country
        )
    
    total_waiting = AreaWaitlist.get_total_waiting(
        location.normalized_postal,
        location.country
    )
    
    return Response({
        'on_waitlist': on_waitlist,
        'position': position,
        'total_waiting': total_waiting,
        'postal_code': location.display_postal,
        'country': location.country
    })
