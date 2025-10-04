import json
import logging
import stripe
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils.dateparse import parse_date, parse_time

from chefs.models import Chef
from local_chefs.geo import ensure_postal_code_coordinates
from .models import ChefServiceOffering, ChefServicePriceTier, ChefServiceOrder
from .serializers import (
    ChefServiceOfferingSerializer,
    ChefServicePriceTierSerializer,
    ChefServiceOrderSerializer,
    PublicChefServiceOfferingSerializer,
)
from .payments import create_service_checkout_session
from .tasks import sync_pending_service_tiers


logger = logging.getLogger(__name__)


def _haversine_miles(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2

    R = 3958.8  # Earth radius in miles
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _normalize_country(code):
    if not code:
        return 'US'
    return str(getattr(code, 'code', code)).upper()


def _resolve_viewer_coordinates(request):
    postal_code = request.query_params.get('postal_code')
    country = request.query_params.get('country')
    if postal_code:
        postal_row = ensure_postal_code_coordinates(postal_code, country or 'US')
        if postal_row and postal_row.latitude is not None and postal_row.longitude is not None:
            return float(postal_row.latitude), float(postal_row.longitude)

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None

    address = getattr(user, 'address', None)
    if not address:
        return None

    if address.latitude is not None and address.longitude is not None:
        return float(address.latitude), float(address.longitude)

    if address.input_postalcode and address.country:
        postal_row = ensure_postal_code_coordinates(address.input_postalcode, address.country)
        if postal_row and postal_row.latitude is not None and postal_row.longitude is not None:
            return float(postal_row.latitude), float(postal_row.longitude)

    return None


def _chef_coordinates(chef):
    # Prefer existing geocoded service postal codes
    postal = chef.serving_postalcodes.filter(latitude__isnull=False, longitude__isnull=False).first()
    if postal:
        return float(postal.latitude), float(postal.longitude)

    # Attempt to geocode the first service postal code
    any_postal = chef.serving_postalcodes.first()
    if any_postal:
        ensured = ensure_postal_code_coordinates(any_postal.code, any_postal.country)
        if ensured and ensured.latitude is not None and ensured.longitude is not None:
            return float(ensured.latitude), float(ensured.longitude)

    # Fall back to chef's address
    address = getattr(chef.user, 'address', None)
    if address:
        if address.latitude is not None and address.longitude is not None:
            return float(address.latitude), float(address.longitude)
        if address.input_postalcode and address.country:
            ensured = ensure_postal_code_coordinates(address.input_postalcode, address.country)
            if ensured and ensured.latitude is not None and ensured.longitude is not None:
                return float(ensured.latitude), float(ensured.longitude)

    return None


def _get_request_chef_or_403(request):
    chef = Chef.objects.filter(user=request.user).first()
    if not chef:
        return None
    return chef


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def offerings(request):
    """
    GET: Public discovery with optional filters (chef_id, service_type) but require auth to match existing pattern.
    POST: Create an offering for the authenticated chef.
    """
    if request.method == 'POST':
        if not request.user or not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)
        chef = _get_request_chef_or_403(request)
        if not chef:
            return Response({"error": "Only chefs can create offerings"}, status=403)
        data = request.data.copy()
        data['chef'] = chef.id
        serializer = ChefServiceOfferingSerializer(data=data)
        if serializer.is_valid():
            offering = serializer.save(chef=chef)
            return Response(ChefServiceOfferingSerializer(offering).data, status=201)
        return Response(serializer.errors, status=400)

    # GET
    chef_id = request.query_params.get('chef_id')
    service_type = request.query_params.get('service_type')
    qs = ChefServiceOffering.objects.filter(active=True)
    if chef_id:
        qs = qs.filter(chef_id=chef_id)
    if service_type:
        qs = qs.filter(service_type=service_type)
    # Hide offerings without any active tier
    qs = qs.prefetch_related(Prefetch('tiers', queryset=ChefServicePriceTier.objects.filter(active=True)))
    viewer_coords = _resolve_viewer_coordinates(request)
    results = []
    for off in qs:
        if off.tiers.all().exists():
            if viewer_coords and off.max_travel_miles is not None:
                chef_coords = _chef_coordinates(off.chef)
                if not chef_coords:
                    logger.warning(
                        "Skipping offering %s for chef %s due to missing coordinates",
                        off.id,
                        off.chef_id,
                    )
                    continue
                distance = _haversine_miles(viewer_coords[0], viewer_coords[1], chef_coords[0], chef_coords[1])
                if distance > float(off.max_travel_miles):
                    continue
            results.append(off)
    serializer = PublicChefServiceOfferingSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_offering(request, offering_id):
    offering = get_object_or_404(ChefServiceOffering, id=offering_id)
    if offering.chef.user_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)
    serializer = ChefServiceOfferingSerializer(offering, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_offerings(request):
    chef = _get_request_chef_or_403(request)
    if not chef:
        return Response({"error": "Only chefs can list their offerings"}, status=403)
    qs = ChefServiceOffering.objects.filter(chef=chef).prefetch_related('tiers')
    return Response(ChefServiceOfferingSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_tier(request, offering_id):
    offering = get_object_or_404(ChefServiceOffering, id=offering_id)
    if offering.chef.user_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)
    data = request.data.copy()
    # Prevent client from setting stripe_price_id/sync fields
    for forbidden in ('stripe_price_id', 'price_sync_status', 'last_price_sync_error', 'price_synced_at', 'offering'):
        data.pop(forbidden, None)
    serializer = ChefServicePriceTierSerializer(data=data)
    if serializer.is_valid():
        tier = ChefServicePriceTier(
            offering=offering,
            **{k: v for k, v in serializer.validated_data.items()}
        )
        try:
            tier.full_clean()
            # New tier should be marked pending for sync
            tier.price_sync_status = 'pending'
            tier.last_price_sync_error = None
            tier.price_synced_at = None
            tier.save()
            try:
                sync_pending_service_tiers.delay()
            except Exception:
                logger.exception("Failed to enqueue service tier sync task")
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        return Response(ChefServicePriceTierSerializer(tier).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_tier(request, tier_id):
    tier = get_object_or_404(ChefServicePriceTier, id=tier_id)
    if tier.offering.chef.user_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)
    # Whitelist updatable fields to prevent mass assignment
    allowed = {
        'household_min', 'household_max', 'currency',
        'is_recurring', 'recurrence_interval', 'active', 'display_label',
        'desired_unit_amount_cents',
    }
    price_related = {'currency', 'is_recurring', 'recurrence_interval', 'desired_unit_amount_cents'}
    touched_price = False
    for field, value in request.data.items():
        if field in allowed:
            setattr(tier, field, value)
            if field in price_related:
                touched_price = True
    try:
        tier.full_clean()
        if touched_price:
            tier.price_sync_status = 'pending'
            tier.last_price_sync_error = None
            tier.price_synced_at = None
        tier.save()
        if touched_price:
            try:
                sync_pending_service_tiers.delay()
            except Exception:
                logger.exception("Failed to enqueue service tier sync task")
    except Exception as e:
        return Response({"error": str(e)}, status=400)
    return Response(ChefServicePriceTierSerializer(tier).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Create a draft ChefServiceOrder.
    Body: offering_id, household_size, schedule/address; optional tier_id.
    If tier_id not provided, server selects a tier if exactly one tier matches.
    """
    customer = request.user
    offering_id = request.data.get('offering_id')
    household_size = request.data.get('household_size')
    tier_id = request.data.get('tier_id')

    if not offering_id or not household_size:
        return Response({"error": "offering_id and household_size are required"}, status=400)

    offering = get_object_or_404(ChefServiceOffering, id=offering_id, active=True)
    chef = offering.chef

    # Resolve tier
    tier = None
    if tier_id:
        tier = get_object_or_404(ChefServicePriceTier, id=tier_id, offering=offering, active=True)
    else:
        size = int(household_size)
        tiers = offering.tiers.filter(active=True)
        candidates = []
        for t in tiers:
            max_sz = t.household_max or 10**9
            if t.household_min <= size <= max_sz:
                candidates.append(t)
        if len(candidates) == 1:
            tier = candidates[0]
        else:
            return Response({"error": "Could not uniquely determine a tier for the given household size"}, status=400)

    # Parse and validate schedule types
    sd = request.data.get('service_date')
    st = request.data.get('service_start_time')
    parsed_date = parse_date(sd) if isinstance(sd, str) else sd
    parsed_time = parse_time(st) if isinstance(st, str) else st

    # Address ownership (if provided)
    address_id = request.data.get('address_id')
    if address_id:
        from custom_auth.models import Address
        try:
            addr = Address.objects.get(id=address_id)
            if addr.user_id != request.user.id:
                return Response({"error": "Invalid address for this user"}, status=403)
        except Address.DoesNotExist:
            return Response({"error": "Address not found"}, status=404)

    # Duration
    dur = request.data.get('duration_minutes')
    duration = None
    if dur is not None and dur != "":
        try:
            duration = int(dur)
            if duration <= 0:
                duration = None
        except Exception:
            duration = None
    if duration is None:
        duration = offering.default_duration_minutes

    order = ChefServiceOrder(
        customer=customer,
        chef=chef,
        offering=offering,
        tier=tier,
        household_size=int(household_size),
        service_date=parsed_date,
        service_start_time=parsed_time,
        duration_minutes=duration,
        address_id=address_id,
        special_requests=request.data.get('special_requests', ''),
        schedule_preferences=request.data.get('schedule_preferences'),
        status='draft',
    )
    try:
        order.full_clean()
        order.save()
    except Exception as e:
        return Response({"error": str(e)}, status=400)

    return Response(ChefServiceOrderSerializer(order).data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order(request, order_id):
    order = get_object_or_404(ChefServiceOrder, id=order_id)
    if order.customer_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)
    return Response(ChefServiceOrderSerializer(order).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    chef = _get_request_chef_or_403(request)
    if not chef:
        return Response({"error": "Only chefs can view service orders"}, status=403)

    qs = (
        ChefServiceOrder.objects
        .filter(chef=chef)
        .select_related('offering', 'tier', 'customer')
        .order_by('-created_at')
    )
    return Response(ChefServiceOrderSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout_order(request, order_id):
    order = get_object_or_404(ChefServiceOrder, id=order_id)
    if order.customer_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)

    # Disallow re-checkout if already processed
    if order.status not in ("draft", "awaiting_payment"):
        if order.status == 'confirmed':
            return Response({
                "success": True,
                "already_paid": True,
                "status": order.status,
            })
        return Response({"error": f"Order is {order.status}; cannot create checkout session"}, status=400)

    # If awaiting_payment and we have a session, return it
    if order.status == 'awaiting_payment' and order.stripe_session_id:
        try:
            from django.conf import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            sess = stripe.checkout.Session.retrieve(order.stripe_session_id)
            return Response({"success": True, "session_id": sess.id, "session_url": getattr(sess, 'url', None)})
        except Exception:
            # Fall through to create a new session if retrieval fails
            pass

    ok, payload = create_service_checkout_session(order.id, customer_email=request.user.email)
    if not ok:
        return Response(payload, status=400)
    return Response({"success": True, **payload})
 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order(request, order_id):
    order = get_object_or_404(ChefServiceOrder, id=order_id)
    if order.customer_id != request.user.id and not request.user.is_staff:
        return Response({"error": "Forbidden"}, status=403)
    if order.status in ("confirmed", "awaiting_payment"):
        # Business rules TBD; allow simple cancellation for now
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        return Response({"status": "cancelled"})
    order.status = 'cancelled'
    order.save(update_fields=['status'])
    return Response({"status": "cancelled"})
