from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import login_required
from .forms import ChefProfileForm, ChefPhotoForm
from .models import Chef, ChefRequest, ChefPhoto
from meals.models import Dish, Meal
from .forms import MealForm
from .decorators import chef_required
from meals.forms import IngredientForm 
from custom_auth.models import UserRole
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import ChefPublicSerializer, ChefMeUpdateSerializer, ChefPhotoSerializer
from .models import ChefWaitlistConfig, ChefWaitlistSubscription, ChefAvailabilityState
from django.utils import timezone
from django.db.models import F, Q
from meals.models import (
    ChefMealEvent, ChefMealOrder, PaymentLog,
    STATUS_SCHEDULED, STATUS_OPEN, STATUS_CANCELLED, STATUS_COMPLETED,
    STATUS_PLACED, STATUS_CONFIRMED,
)
from custom_auth.models import Address
from django_countries import countries
import os
import requests
import traceback
import logging
from local_chefs.models import PostalCode, ChefPostalCode
from django.db import transaction
import stripe

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

def chef_list(request):
    return HttpResponseBadRequest('Legacy endpoint removed')


def chef_detail(request, chef_id):
    return HttpResponseBadRequest('Legacy endpoint removed')


@login_required
def chef_request(request):
    return HttpResponseBadRequest('Legacy endpoint removed')


@login_required
@chef_required
def chef_view(request):
    return HttpResponseBadRequest('Legacy endpoint removed')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_chef_status(request):
    """
    Check if a user is a chef or has a pending chef request
    """
    user = request.user
    
    # Check if user is a chef
    is_chef = Chef.objects.filter(user=user).exists()
    
    # Check if user has a pending chef request
    has_pending_request = ChefRequest.objects.filter(
        user=user, 
        is_approved=False
    ).exists()
    
    return JsonResponse({
        'is_chef': is_chef,
        'has_pending_request': has_pending_request
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_chef_request(request):
    """
    Submit a new chef request or update an existing one
    """
    try:
        # Validate required fields
        required_fields = ['user_id', 'experience', 'bio', 'city', 'country']
        missing_fields = [field for field in required_fields if not request.data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'required_fields': required_fields,
                'received_data': {
                    'data': dict(request.data),
                    'post': dict(request.POST),
                    'files': bool(request.FILES)
                }
            }, status=400)

        user_id = request.data.get('user_id')
        
        try:
            from custom_auth.models import CustomUser
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": f"User with ID {user_id} not found", "source":"submit_chef_request", "traceback": traceback.format_exc()})
            return JsonResponse({
                'error': f'User with ID {user_id} not found',
                'received_user_id': user_id
            }, status=404)
        
        # Check if user is already a chef
        if Chef.objects.filter(user=user).exists():
            return JsonResponse({
                'error': 'User is already a chef',
                'user_id': user_id
            }, status=400)
        
        # Check if user already has a pending request
        existing_request = ChefRequest.objects.filter(user=user).first()
        if existing_request:
            if not existing_request.is_approved:
                return JsonResponse({
                    'error': 'User already has a pending chef request',
                    'request_id': existing_request.id,
                    'user_id': user_id
                }, status=409)
            else:
                chef_request = existing_request
        else:
            chef_request = ChefRequest(user=user)
        
        # Validate and resolve country (accepts code like "US" or full name like "United States")
        country_input = request.data.get('country')
        def _resolve_country_code(value: str):
            if not value:
                return None
            candidate = value.strip()
            # If looks like a 2-letter code and is valid
            if len(candidate) == 2:
                for code, _name in countries:
                    if code.upper() == candidate.upper():
                        return code.upper()
            # Otherwise try name lookup
            for code, name in countries:
                if name.lower() == candidate.lower():
                    return code
            return None

        country_code = _resolve_country_code(country_input)
        if not country_code:
            return JsonResponse({
                'error': 'Invalid country provided. Use ISO code (e.g., "US") or full country name (e.g., "United States").',
                'received_country': country_input
            }, status=400)

        # Ensure city present (already checked above) and persist to user's Address
        city_value = request.data.get('city')
        try:
            address, _created = Address.objects.get_or_create(user=user)
            address.city = city_value
            address.country = country_code
            address.save(update_fields=['city', 'country'])
        except Exception as e:
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": f"Failed to save address info for chef request: {str(e)}", "source":"submit_chef_request", "traceback": traceback.format_exc()})
            return JsonResponse({
                'error': 'Failed to save address info for chef request',
                'details': str(e)
            }, status=500)

        # Update chef request with new data
        try:
            chef_request.experience = request.data.get('experience', '')
            chef_request.bio = request.data.get('bio', '')
            
            # Handle profile pic if provided
            if 'profile_pic' in request.FILES:
                try:
                    profile_pic = request.FILES['profile_pic']
                    
                    # Get file extension
                    file_ext = os.path.splitext(profile_pic.name)[1].lower()
                    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
                    
                    # Check either content type or file extension
                    allowed_types = ['image/jpeg', 'image/png', 'image/gif']
                    is_valid_type = (profile_pic.content_type in allowed_types) or (file_ext in allowed_extensions)
                    if not is_valid_type:
                        return JsonResponse({
                            'error': 'Invalid file type',
                            'details': f'File must be a valid image (jpg, jpeg, png, or gif)',
                            'received_type': profile_pic.content_type,
                            'file_extension': file_ext
                        }, status=400)
                    
                    # Validate file size (max 5MB)
                    if profile_pic.size > 5 * 1024 * 1024:
                        return JsonResponse({
                            'error': 'File too large',
                            'details': 'Profile picture must be less than 5MB',
                            'received_size': profile_pic.size
                        }, status=400)
                    
                    chef_request.profile_pic = profile_pic
                except Exception as e:
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": f"Failed to process profile picture", "source":"submit_chef_request", "traceback": traceback.format_exc()})
                    return JsonResponse({
                        'error': 'Failed to process profile picture',
                        'details': str(e)
                    }, status=400)
            
            chef_request.save()
            
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": f"Failed to save chef request", "source":"submit_chef_request", "traceback": traceback.format_exc()})
            return JsonResponse({
                'error': 'Failed to save chef request',
                'details': str(e)
            }, status=500)
        
        # Handle postal codes (use provided country)
        postal_codes = request.data.get('postal_codes', [])
        # Ensure postal_codes is a list
        if not isinstance(postal_codes, list):
            postal_codes = [postal_codes] if postal_codes else []
        if postal_codes:
            try:
                from local_chefs.models import PostalCode
                # Clear existing postal codes
                chef_request.requested_postalcodes.clear()
                
                processed_codes = []
                failed_codes = []
                
                # Add new postal codes
                for code in postal_codes:
                    try:
                        # Normalize and get/create per country
                        postal_code, _created_pc = PostalCode.get_or_create_normalized(code, country_code)
                        chef_request.requested_postalcodes.add(postal_code)
                        processed_codes.append(code)
                    except Exception as e:
                        # n8n traceback
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        requests.post(n8n_traceback_url, json={"error": f"Error processing postal code {code}: {str(e)}", "source":"submit_chef_request", "traceback": traceback.format_exc()})
                        failed_codes.append({'code': code, 'error': str(e)})
                
                if failed_codes:
                    logger.error(f"Some postal codes failed: {failed_codes}")
                
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": f"Failed to process postal codes", "source":"submit_chef_request", "traceback": traceback.format_exc()})
                return JsonResponse({
                    'error': 'Failed to process postal codes',
                    'details': str(e),
                    'processed_codes': processed_codes,
                    'failed_codes': failed_codes
                }, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Chef request submitted successfully',
            'request_id': chef_request.id,
            'user_id': user_id,
            'processed_postal_codes': processed_codes if postal_codes else [],
            'profile_pic_saved': 'profile_pic' in request.FILES
        })
        
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": f"Unexpected error in submit_chef_request: {str(e)}", "source":"submit_chef_request", "traceback": traceback.format_exc()})
        return JsonResponse({
            'error': 'An unexpected error occurred',
            'details': str(e),
            'request_data': dict(request.data)
        }, status=500)


# React API for chef profile and photos
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_chef_profile(request):
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure user is in chef mode and approved
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return Response({'detail': 'Switch to chef mode to access profile'}, status=status.HTTP_403_FORBIDDEN)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Switch to chef mode to access profile'}, status=status.HTTP_403_FORBIDDEN)
    # Ignore any stray user_id in query/body
    if 'user_id' in request.query_params or 'user_id' in request.data:
        pass
    serializer = ChefPublicSerializer(chef, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def me_update_profile(request):
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure user is in chef mode and approved
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return Response({'detail': 'Switch to chef mode to update profile'}, status=status.HTTP_403_FORBIDDEN)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Switch to chef mode to update profile'}, status=status.HTTP_403_FORBIDDEN)
    # Ignore any stray user_id in query/body
    if 'user_id' in request.query_params or 'user_id' in request.data:
        pass
    serializer = ChefMeUpdateSerializer(chef, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(ChefPublicSerializer(chef, context={'request': request}).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def me_upload_photo(request):
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure user is in chef mode and approved
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return Response({'detail': 'Switch to chef mode to upload photos'}, status=status.HTTP_403_FORBIDDEN)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Switch to chef mode to upload photos'}, status=status.HTTP_403_FORBIDDEN)
    # Ignore any stray user_id in query/body
    if 'user_id' in request.query_params or 'user_id' in request.data:
        pass

    form = ChefPhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

    photo = form.save(commit=False)
    photo.chef = chef
    if photo.is_featured:
        ChefPhoto.objects.filter(chef=chef, is_featured=True).update(is_featured=False)
    photo.save()
    return Response(ChefPhotoSerializer(photo, context={'request': request}).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def me_delete_photo(request, photo_id):
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)
    # Ensure user is in chef mode and approved
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return Response({'detail': 'Switch to chef mode to delete photos'}, status=status.HTTP_403_FORBIDDEN)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Switch to chef mode to delete photos'}, status=status.HTTP_403_FORBIDDEN)
    photo = get_object_or_404(ChefPhoto, id=photo_id, chef=chef)
    photo.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def me_set_break(request):
    """
    Toggle a chef's break status. When enabling break, cancel all upcoming events and refund paid orders.

    Request JSON:
    - is_on_break: bool (required)
    - reason: str (optional; defaults to "Chef is on break")

    Response JSON (when enabling break):
    - is_on_break: true
    - cancelled_events: int
    - orders_cancelled: int
    - refunds_processed: int
    - refunds_failed: int
    - errors: [str]
    """
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)

    # Ensure user is in chef mode and approved
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return Response({'detail': 'Switch to chef mode to modify break status'}, status=status.HTTP_403_FORBIDDEN)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Switch to chef mode to modify break status'}, status=status.HTTP_403_FORBIDDEN)

    is_on_break = request.data.get('is_on_break', None)
    if is_on_break is None:
        return Response({'error': 'is_on_break is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(is_on_break, bool):
        return Response({'error': 'is_on_break must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason') or 'Chef is going on break'

    # Turning OFF break: just flip the flag
    if is_on_break is False:
        chef.is_on_break = False
        chef.save(update_fields=['is_on_break'])
        return Response({'is_on_break': False})

    # Turning ON break: set flag, then cancel upcoming events + refund
    chef.is_on_break = True
    chef.save(update_fields=['is_on_break'])

    today = timezone.now().date()
    # Future/present events not already finalized
    events_qs = (
        ChefMealEvent.objects
        .filter(chef=chef)
        .exclude(status__in=[STATUS_CANCELLED, STATUS_COMPLETED])
        .filter(event_date__gte=today)
        .order_by('event_date', 'event_time')
    )

    cancelled_events = 0
    orders_cancelled = 0
    refunds_processed = 0
    refunds_failed = 0
    errors = []

    for event in events_qs:
        try:
            with transaction.atomic():
                # Cancel all active orders on this event
                orders = ChefMealOrder.objects.select_for_update().filter(
                    meal_event=event,
                    status__in=[STATUS_PLACED, STATUS_CONFIRMED]
                )

                for order in orders:
                    prev_status = order.status
                    order.status = STATUS_CANCELLED
                    # Non-persistent attribute used by some email templates; safe if absent
                    try:
                        order.cancellation_reason = f'Event cancelled by chef: {reason}'
                    except Exception:
                        pass
                    order.save(update_fields=['status'])
                    orders_cancelled += 1

                    # If previously confirmed and paid, refund
                    if prev_status == STATUS_CONFIRMED and order.stripe_payment_intent_id:
                        try:
                            refund = stripe.Refund.create(payment_intent=order.stripe_payment_intent_id)
                            # Persist refund id if field exists
                            try:
                                order.stripe_refund_id = refund.id
                                order.save(update_fields=['stripe_refund_id'])
                            except Exception:
                                pass
                            # Log payment
                            try:
                                PaymentLog.objects.create(
                                    chef_meal_order=order,
                                    user=order.customer,
                                    chef=chef,
                                    action='refund',
                                    amount=(order.price_paid or 0) * (order.quantity or 1),
                                    stripe_id=refund.id,
                                    status='succeeded',
                                    details={'reason': 'Chef break – bulk cancellation'},
                                )
                            except Exception:
                                pass
                            # Notify user
                            try:
                                from meals.email_service import (
                                    send_refund_notification_email,
                                    send_order_cancellation_email,
                                )
                                send_refund_notification_email.delay(order.id)
                                send_order_cancellation_email.delay(order.id)
                            except Exception:
                                pass
                            refunds_processed += 1
                        except Exception as e:
                            refunds_failed += 1
                            errors.append(f"Order {order.id} refund failed: {str(e)}")
                            # Still send cancellation email
                            try:
                                from meals.email_service import send_order_cancellation_email
                                send_order_cancellation_email.delay(order.id)
                            except Exception:
                                pass

                # Finally, cancel the event itself
                event.status = STATUS_CANCELLED
                event.cancellation_reason = reason if hasattr(event, 'cancellation_reason') else getattr(event, 'cancellation_reason', None)
                event.cancellation_date = timezone.now() if hasattr(event, 'cancellation_date') else getattr(event, 'cancellation_date', None)
                event.save(update_fields=['status'])
                cancelled_events += 1
        except Exception as e:
            errors.append(f"Event {event.id} cancellation error: {str(e)}")

    return Response({
        'is_on_break': True,
        'cancelled_events': cancelled_events,
        'orders_cancelled': orders_cancelled,
        'refunds_processed': refunds_processed,
        'refunds_failed': refunds_failed,
        'errors': errors,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def chef_public(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)
    # Ensure approved – presence of Chef row generally indicates approval; optionally check UserRole
    try:
        user_role = UserRole.objects.get(user=chef.user)
        if not user_role.is_chef:
            return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ChefPublicSerializer(chef, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def chef_public_by_username(request, username):
    chef = Chef.objects.filter(user__username__iexact=username).first()
    if not chef:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        user_role = UserRole.objects.get(user=chef.user)
        if not user_role.is_chef:
            return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = ChefPublicSerializer(chef, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def chef_lookup_by_username(request, username):
    chef = Chef.objects.filter(user__username__iexact=username).first()
    if not chef:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        user_role = UserRole.objects.get(user=chef.user)
        if not user_role.is_chef:
            return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    except UserRole.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'id': chef.user.id, 'chef_id': chef.id})


@api_view(['GET'])
@permission_classes([AllowAny])
def chef_public_directory(request):
    from django.db.models import Count, Q
    queryset = Chef.objects.all()

    # Only approved chefs
    queryset = queryset.filter(user__userrole__is_chef=True)

    q = request.query_params.get('q')
    serves_postal = request.query_params.get('serves_postal')
    country = request.query_params.get('country')
    ordering = request.query_params.get('ordering')

    if q:
        queryset = queryset.filter(
            Q(user__username__icontains=q) |
            Q(serving_postalcodes__code__icontains=q) |
            Q(serving_postalcodes__display_code__icontains=q)
        )

    if serves_postal:
        from local_chefs.models import PostalCode
        normalized = PostalCode.normalize_code(serves_postal)
        queryset = queryset.filter(serving_postalcodes__code=normalized)

    if country:
        queryset = queryset.filter(serving_postalcodes__country=country)

    queryset = queryset.distinct()

    if ordering == 'popular':
        queryset = queryset.annotate(num_events=Count('meal_events')).order_by('-num_events', '-id')
    elif ordering == 'recent':
        queryset = queryset.order_by('-id')
    else:
        # Ensure deterministic ordering for pagination
        queryset = queryset.order_by('id')

    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    page_size = request.query_params.get('page_size')
    if page_size:
        try:
            paginator.page_size = max(1, min(100, int(page_size)))
        except Exception:
            paginator.page_size = 12
    page = paginator.paginate_queryset(queryset, request)
    serializer = ChefPublicSerializer(page or queryset, many=True, context={'request': request})
    if page is not None:
        return paginator.get_paginated_response(serializer.data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chef_serves_my_area(request, chef_id):
    try:
        chef = Chef.objects.get(id=chef_id)
    except Chef.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)

    address = getattr(request.user, 'address', None)
    if not address or not address.input_postalcode or not address.country:
        return Response({
            'serves': False,
            'detail': 'Missing user address country or postal code'
        }, status=status.HTTP_400_BAD_REQUEST)

    normalized_code = PostalCode.normalize_code(address.input_postalcode)
    serves = ChefPostalCode.objects.filter(
        chef=chef,
        postal_code__code=normalized_code,
        postal_code__country=address.country
    ).exists()

    return Response({
        'serves': serves,
        'chef_id': chef.id,
        'user_postal_code': address.display_postalcode or address.input_postalcode,
        'user_country': address.country.code if hasattr(address.country, 'code') else str(address.country)
    })


# =========================
# Waitlist API Endpoints
# =========================

@api_view(['GET'])
@permission_classes([AllowAny])
def waitlist_config(request):
    # Simplified: treat waitlist as enabled by default
    cfg = ChefWaitlistConfig.get_config()
    enabled = True if cfg is None else bool(getattr(cfg, 'enabled', True))
    return Response({'enabled': enabled})


def _count_upcoming_events(chef_id):
    now = timezone.now()
    return ChefMealEvent.objects.filter(
        chef_id=chef_id,
        status__in=[STATUS_SCHEDULED, STATUS_OPEN],
        order_cutoff_time__gt=now,
        orders_count__lt=F('max_orders')
    ).count()


@api_view(['GET'])
@permission_classes([AllowAny])
def waitlist_status(request, chef_id):
    try:
        chef = Chef.objects.get(id=chef_id)
    except Chef.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)

    # Simplified: waitlist is enabled by default
    enabled = True
    upcoming = _count_upcoming_events(chef.id)

    subscribed = False
    can_subscribe = False
    if getattr(request, 'user', None) and request.user.is_authenticated:
        subscribed = ChefWaitlistSubscription.objects.filter(user=request.user, chef=chef, active=True).exists()
        # Allow subscribing if chef is on break or has no upcoming orderable events
        can_subscribe = enabled and not subscribed and (chef.is_on_break or upcoming == 0)

    return Response({
        'enabled': enabled,
        'subscribed': subscribed,
        'can_subscribe': can_subscribe,
        'chef_is_on_break': chef.is_on_break,
        'upcoming_events_count': upcoming,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def waitlist_subscribe(request, chef_id):
    try:
        chef = Chef.objects.get(id=chef_id)
    except Chef.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)

    sub, created = ChefWaitlistSubscription.objects.get_or_create(
        user=request.user,
        chef=chef,
        active=True,
        defaults={}
    )
    return Response({'status': 'ok', 'subscribed': True})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def waitlist_unsubscribe(request, chef_id):
    try:
        chef = Chef.objects.get(id=chef_id)
    except Chef.DoesNotExist:
        return Response({'detail': 'Chef not found'}, status=status.HTTP_404_NOT_FOUND)
    updated = ChefWaitlistSubscription.objects.filter(user=request.user, chef=chef, active=True).update(active=False)
    if updated == 0:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
