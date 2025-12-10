from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import ChefPostalCode, PostalCode, AdministrativeArea
from .serializers import (
    AdministrativeAreaSearchSerializer,
    AdministrativeAreaSerializer,
    PostalCodeMinimalSerializer,
    ChefServiceAreaSerializer,
)
from chefs.models import Chef
from custom_auth.models import Address, CustomUser


def chef_service_areas(request, query):
    """Legacy endpoint - returns chef service areas by chef name query."""
    normalized_query = query.strip().lower()
    chefs = Chef.objects.filter(user__username__icontains=normalized_query)

    if not chefs.exists():
        return JsonResponse({'error': 'No chefs found based on the query provided'})

    auth_chef_result = []
    for chef in chefs:
        postal_codes_served = ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True)
        chef_info = {
            "chef_id": chef.id,
            "name": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
            'service_postal_codes': list(postal_codes_served),
        }
        auth_chef_result.append(chef_info)
    return {"auth_chef_result": auth_chef_result}


def service_area_chefs(request):
    """Legacy endpoint - returns chefs serving a user's postal code."""
    user_id = request.data.get('user_id')
    user = CustomUser.objects.get(id=user_id)
    address = Address.objects.get(user=user)
    user_input_postalcode = address.input_postalcode

    try:
        user_postalcode = PostalCode.objects.get(code=user_input_postalcode)
        chefs = Chef.objects.filter(serving_postalcodes=user_postalcode)

        chef_result = []
        for chef in chefs:
            postal_codes_served = ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True)
            chef_info = {
                "chef_id": chef.id,
                "name": chef.user.username,
                "experience": chef.experience,
                "bio": chef.bio,
                "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
                'service_postal_codes': list(postal_codes_served),
            }
            chef_result.append(chef_info)
        return {'chefs': chef_result}
    except PostalCode.DoesNotExist:
        return {'message': 'We do not serve your area yet. Please check back later.'}


# ============================================================================
# NEW API ENDPOINTS FOR SERVICE AREA PICKER
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def search_areas(request):
    """
    Search administrative areas by name.
    
    Query params:
        q: Search query (required, min 2 chars)
        country: Filter by country code (optional)
        type: Filter by area type (optional)
        limit: Max results (default 20, max 100)
    
    Returns:
        List of matching areas with postal code counts
    """
    query = request.query_params.get('q', '').strip()
    country = request.query_params.get('country', '').strip().upper()
    area_type = request.query_params.get('type', '').strip()
    limit = min(int(request.query_params.get('limit', 20)), 100)
    
    if len(query) < 2:
        return Response({'results': [], 'message': 'Query too short'})
    
    # Build queryset
    qs = AdministrativeArea.objects.select_related('parent')
    
    # Search in name and name_local
    qs = qs.filter(
        Q(name__icontains=query) | Q(name_local__icontains=query)
    )
    
    if country:
        qs = qs.filter(country=country)
    
    if area_type:
        qs = qs.filter(area_type=area_type)
    
    # Order by postal code count (most useful areas first) then name
    qs = qs.order_by('-postal_code_count', 'name')[:limit]
    
    serializer = AdministrativeAreaSearchSerializer(qs, many=True)
    return Response({'results': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_area(request, area_id):
    """
    Get details for a specific administrative area.
    """
    try:
        area = AdministrativeArea.objects.select_related('parent').get(id=area_id)
    except AdministrativeArea.DoesNotExist:
        return Response({'error': 'Area not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = AdministrativeAreaSerializer(area)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_area_postal_codes(request, area_id):
    """
    Get all postal codes within an administrative area.
    
    Query params:
        include_children: Include postal codes from child areas (default true)
    """
    try:
        area = AdministrativeArea.objects.get(id=area_id)
    except AdministrativeArea.DoesNotExist:
        return Response({'error': 'Area not found'}, status=status.HTTP_404_NOT_FOUND)
    
    include_children = request.query_params.get('include_children', 'true').lower() == 'true'
    
    if include_children:
        postal_codes = area.get_all_postal_codes()
    else:
        postal_codes = area.postal_codes.all()
    
    serializer = PostalCodeMinimalSerializer(postal_codes, many=True)
    return Response({
        'area': AdministrativeAreaSearchSerializer(area).data,
        'postal_codes': serializer.data,
        'total': postal_codes.count()
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_areas_by_country(request, country_code):
    """
    Get top-level administrative areas for a country (states/prefectures).
    
    Useful for populating initial map view or dropdown.
    """
    country_code = country_code.upper()
    
    # Get top-level areas (no parent)
    areas = AdministrativeArea.objects.filter(
        country=country_code,
        parent__isnull=True
    ).order_by('name')
    
    serializer = AdministrativeAreaSearchSerializer(areas, many=True)
    return Response({'results': serializer.data, 'country': country_code})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_area_children(request, area_id):
    """
    Get child areas of an administrative area.
    
    E.g., get all cities in a prefecture, or all wards in a city.
    """
    try:
        area = AdministrativeArea.objects.get(id=area_id)
    except AdministrativeArea.DoesNotExist:
        return Response({'error': 'Area not found'}, status=status.HTTP_404_NOT_FOUND)
    
    children = area.children.all().order_by('name')
    serializer = AdministrativeAreaSearchSerializer(children, many=True)
    return Response({
        'parent': AdministrativeAreaSearchSerializer(area).data,
        'children': serializer.data
    })


# ============================================================================
# CHEF SERVICE AREA MANAGEMENT
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chef_service_areas(request):
    """
    Get the current chef's service areas grouped by administrative area.
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get all postal codes the chef serves
    chef_postal_codes = ChefPostalCode.objects.filter(chef=chef).select_related(
        'postal_code', 'postal_code__admin_area', 'postal_code__admin_area__parent'
    )
    
    # Group by admin area
    areas_dict = {}
    ungrouped_codes = []
    
    for cpc in chef_postal_codes:
        pc = cpc.postal_code
        if pc.admin_area:
            area = pc.admin_area
            if area.id not in areas_dict:
                areas_dict[area.id] = {
                    'area': area,
                    'postal_codes': [],
                    'count': 0
                }
            areas_dict[area.id]['postal_codes'].append(pc)
            areas_dict[area.id]['count'] += 1
        else:
            ungrouped_codes.append(pc)
    
    # Serialize
    areas_data = []
    for area_info in areas_dict.values():
        area = area_info['area']
        areas_data.append({
            'area_id': area.id,
            'name': area.name,
            'name_local': area.name_local,
            'area_type': area.area_type,
            'country': str(area.country),
            'parent_name': area.parent.name if area.parent else None,
            'postal_code_count': area_info['count'],
            'total_in_area': area.postal_code_count,
            'latitude': area.latitude,
            'longitude': area.longitude,
        })
    
    ungrouped_data = PostalCodeMinimalSerializer(ungrouped_codes, many=True).data
    
    return Response({
        'areas': areas_data,
        'ungrouped_postal_codes': ungrouped_data,
        'total_postal_codes': chef_postal_codes.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_service_area(request):
    """
    Add an administrative area to chef's service areas.
    This creates ChefPostalCode entries for all postal codes in the area.
    
    Body:
        area_id: ID of the AdministrativeArea to add
        include_children: Whether to include postal codes from child areas (default true)
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    area_id = request.data.get('area_id')
    include_children = request.data.get('include_children', True)
    
    if not area_id:
        return Response({'error': 'area_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        area = AdministrativeArea.objects.get(id=area_id)
    except AdministrativeArea.DoesNotExist:
        return Response({'error': 'Area not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get postal codes in this area
    if include_children:
        postal_codes = area.get_all_postal_codes()
    else:
        postal_codes = area.postal_codes.all()
    
    # Create ChefPostalCode entries
    created_count = 0
    with transaction.atomic():
        for pc in postal_codes:
            _, created = ChefPostalCode.objects.get_or_create(
                chef=chef,
                postal_code=pc
            )
            if created:
                created_count += 1
    
    return Response({
        'success': True,
        'area': AdministrativeAreaSearchSerializer(area).data,
        'added_count': created_count,
        'total_in_area': postal_codes.count()
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_service_area(request, area_id):
    """
    Remove an administrative area from chef's service areas.
    This removes ChefPostalCode entries for all postal codes in the area.
    
    Query params:
        include_children: Whether to remove postal codes from child areas too (default true)
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        area = AdministrativeArea.objects.get(id=area_id)
    except AdministrativeArea.DoesNotExist:
        return Response({'error': 'Area not found'}, status=status.HTTP_404_NOT_FOUND)
    
    include_children = request.query_params.get('include_children', 'true').lower() == 'true'
    
    # Get postal codes in this area
    if include_children:
        postal_codes = area.get_all_postal_codes()
    else:
        postal_codes = area.postal_codes.all()
    
    # Delete ChefPostalCode entries
    deleted_count = ChefPostalCode.objects.filter(
        chef=chef,
        postal_code__in=postal_codes
    ).delete()[0]
    
    return Response({
        'success': True,
        'removed_count': deleted_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_postal_codes(request):
    """
    Add individual postal codes to chef's service area.
    Useful for adding specific codes not in an area or for fine-tuning.
    
    Body:
        postal_codes: List of postal code strings
        country: Country code
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    codes = request.data.get('postal_codes', [])
    country = request.data.get('country', '').upper()
    
    if not codes or not country:
        return Response({'error': 'postal_codes and country required'}, status=status.HTTP_400_BAD_REQUEST)
    
    created_count = 0
    errors = []
    
    with transaction.atomic():
        for code in codes:
            try:
                postal_code, _ = PostalCode.get_or_create_normalized(code, country)
                if postal_code:
                    _, created = ChefPostalCode.objects.get_or_create(
                        chef=chef,
                        postal_code=postal_code
                    )
                    if created:
                        created_count += 1
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})
    
    return Response({
        'success': True,
        'added_count': created_count,
        'errors': errors
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_postal_codes(request):
    """
    Remove individual postal codes from chef's service area.
    
    Body:
        postal_codes: List of postal code strings
        country: Country code
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    codes = request.data.get('postal_codes', [])
    country = request.data.get('country', '').upper()
    
    if not codes or not country:
        return Response({'error': 'postal_codes and country required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Normalize codes
    normalized = [PostalCode.normalize_code(c) for c in codes if c]
    
    # Delete matching ChefPostalCode entries
    deleted_count = ChefPostalCode.objects.filter(
        chef=chef,
        postal_code__code__in=normalized,
        postal_code__country=country
    ).delete()[0]
    
    return Response({
        'success': True,
        'removed_count': deleted_count
    })


# ============================================================================
# SERVICE AREA REQUEST MANAGEMENT (for admin-approved area changes)
# ============================================================================

from .models import ServiceAreaRequest


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chef_area_status(request):
    """
    Get chef's current service areas and any pending requests.
    
    Returns:
        approved_areas: Currently approved service areas (grouped by admin_area)
        ungrouped_postal_codes: Postal codes not linked to an admin area (legacy data)
        pending_requests: Any pending area requests awaiting admin review
        request_history: Recent request history
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get current approved areas (group by admin_area)
    chef_postal_codes = ChefPostalCode.objects.filter(chef=chef).select_related(
        'postal_code', 'postal_code__admin_area', 'postal_code__admin_area__parent'
    )
    
    # Group by admin area, also collect ungrouped postal codes
    areas_dict = {}
    ungrouped_codes = []
    
    for cpc in chef_postal_codes:
        pc = cpc.postal_code
        if pc.admin_area:
            area = pc.admin_area
            if area.id not in areas_dict:
                areas_dict[area.id] = {
                    'area_id': area.id,
                    'name': area.name,
                    'name_local': area.name_local,
                    'area_type': area.area_type,
                    'country': str(area.country),
                    'parent_name': area.parent.name if area.parent else None,
                    'postal_code_count': 0,
                    'latitude': str(area.latitude) if area.latitude else None,
                    'longitude': str(area.longitude) if area.longitude else None,
                }
            areas_dict[area.id]['postal_code_count'] += 1
        else:
            # Postal code not linked to an admin area - include it separately
            ungrouped_codes.append({
                'id': pc.id,
                'code': pc.display_code or pc.code,
                'country': str(pc.country),
                'place_name': pc.place_name or '',
            })
    
    # Get pending requests
    pending_requests = ServiceAreaRequest.objects.filter(
        chef=chef,
        status='pending'
    ).prefetch_related('requested_areas', 'requested_postal_codes')
    
    pending_data = []
    for req in pending_requests:
        pending_data.append({
            'id': req.id,
            'created_at': req.created_at.isoformat(),
            'chef_notes': req.chef_notes,
            'areas': [
                {
                    'id': a.id,
                    'name': a.name,
                    'name_local': a.name_local,
                    'postal_code_count': a.postal_code_count,
                }
                for a in req.requested_areas.all()
            ],
            'postal_code_count': req.requested_postal_codes.count(),
            'total_codes_requested': req.total_postal_codes_requested,
        })
    
    # Get recent history
    history = ServiceAreaRequest.objects.filter(
        chef=chef
    ).exclude(status='pending').order_by('-created_at').prefetch_related(
        'requested_areas', 'approved_areas', 'requested_postal_codes', 'approved_postal_codes'
    )[:10]
    
    history_data = []
    for req in history:
        item = {
            'id': req.id,
            'status': req.status,
            'status_display': req.get_status_display(),
            'created_at': req.created_at.isoformat(),
            'reviewed_at': req.reviewed_at.isoformat() if req.reviewed_at else None,
            'admin_notes': req.admin_notes,
            'areas_count': req.requested_areas.count(),
        }
        
        # Include approval summary for partially approved requests
        if req.status in ['approved', 'partially_approved', 'rejected']:
            summary = req.approval_summary
            if summary:
                item['approval_summary'] = summary
            
            # For partial approvals, include which areas were approved/rejected
            if req.status == 'partially_approved':
                item['approved_areas'] = [
                    {'id': a.id, 'name': a.name, 'postal_code_count': a.postal_code_count}
                    for a in req.approved_areas.all()
                ]
                item['rejected_areas'] = [
                    {'id': a.id, 'name': a.name, 'postal_code_count': a.postal_code_count}
                    for a in req.rejected_areas
                ]
        
        history_data.append(item)
    
    return Response({
        'approved_areas': list(areas_dict.values()),
        'ungrouped_postal_codes': ungrouped_codes,
        'total_postal_codes': chef_postal_codes.count(),
        'pending_requests': pending_data,
        'has_pending': len(pending_data) > 0,
        'request_history': history_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_area_request(request):
    """
    Submit a request to add new service areas.
    
    The chef keeps their existing areas; new areas go through admin review.
    
    Body:
        area_ids: List of AdministrativeArea IDs to request
        postal_codes: List of individual postal code strings (optional)
        country: Country code for postal codes
        notes: Chef's explanation for the request (optional)
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    area_ids = request.data.get('area_ids', [])
    postal_codes = request.data.get('postal_codes', [])
    country = request.data.get('country', '').upper()
    notes = request.data.get('notes', '')
    
    if not area_ids and not postal_codes:
        return Response(
            {'error': 'Please select at least one area or postal code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for existing pending request
    if ServiceAreaRequest.has_pending_request(chef):
        return Response(
            {'error': 'You already have a pending request. Please wait for it to be reviewed.'},
            status=status.HTTP_409_CONFLICT
        )
    
    # Create the request
    area_request = ServiceAreaRequest.objects.create(
        chef=chef,
        chef_notes=notes
    )
    
    # Add requested areas
    valid_areas = []
    for area_id in area_ids:
        try:
            area = AdministrativeArea.objects.get(id=area_id)
            area_request.requested_areas.add(area)
            valid_areas.append(area)
        except AdministrativeArea.DoesNotExist:
            pass
    
    # Add requested postal codes
    valid_codes = []
    for code in postal_codes:
        if code and country:
            try:
                postal_code, _ = PostalCode.get_or_create_normalized(code, country)
                if postal_code:
                    area_request.requested_postal_codes.add(postal_code)
                    valid_codes.append(code)
            except Exception:
                pass
    
    return Response({
        'success': True,
        'request_id': area_request.id,
        'areas_requested': len(valid_areas),
        'postal_codes_requested': len(valid_codes),
        'total_postal_codes': area_request.total_postal_codes_requested,
        'message': 'Your request has been submitted and is pending admin review.'
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancel_area_request(request, request_id):
    """
    Cancel a pending area request.
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        area_request = ServiceAreaRequest.objects.get(
            id=request_id,
            chef=chef,
            status='pending'
        )
    except ServiceAreaRequest.DoesNotExist:
        return Response(
            {'error': 'Pending request not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    area_request.delete()
    
    return Response({
        'success': True,
        'message': 'Request cancelled'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_area_request(request, request_id):
    """
    Get details of a specific area request.
    """
    try:
        chef = request.user.chef
    except Chef.DoesNotExist:
        return Response({'error': 'Not a chef'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        area_request = ServiceAreaRequest.objects.get(id=request_id, chef=chef)
    except ServiceAreaRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'id': area_request.id,
        'status': area_request.status,
        'chef_notes': area_request.chef_notes,
        'admin_notes': area_request.admin_notes,
        'created_at': area_request.created_at.isoformat(),
        'reviewed_at': area_request.reviewed_at.isoformat() if area_request.reviewed_at else None,
        'areas': [
            {
                'id': a.id,
                'name': a.name,
                'name_local': a.name_local,
                'area_type': a.area_type,
                'country': str(a.country),
                'postal_code_count': a.postal_code_count,
            }
            for a in area_request.requested_areas.all()
        ],
        'postal_codes': [
            {
                'id': pc.id,
                'code': pc.display_code or pc.code,
                'country': str(pc.country),
            }
            for pc in area_request.requested_postal_codes.all()
        ],
        'total_postal_codes': area_request.total_postal_codes_requested,
    })