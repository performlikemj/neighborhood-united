"""
Chef Receipt Management API Endpoints

Provides endpoints for chefs to upload and manage receipts for ingredient
purchases, supplies, and other meal plan related expenses.
"""
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from chefs.models import Chef
from meals.models import MealPlanReceipt
from chefs.serializers import (
    MealPlanReceiptSerializer,
    MealPlanReceiptUploadSerializer,
    MealPlanReceiptListSerializer,
)
from custom_auth.models import UserRole


def _get_chef_or_403(request):
    """Helper to get chef for current user, ensuring chef mode is active."""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return None, Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return None, Response(
                {'detail': 'Switch to chef mode to access receipts'},
                status=status.HTTP_403_FORBIDDEN
            )
    except UserRole.DoesNotExist:
        return None, Response(
            {'detail': 'Switch to chef mode to access receipts'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    return chef, None


class ReceiptPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def receipt_list(request):
    """
    GET: List all receipts for the authenticated chef with optional filtering.
    POST: Upload a new receipt.
    
    Query parameters for GET:
    - category: Filter by category (ingredients, supplies, equipment, etc.)
    - customer: Filter by customer ID
    - chef_meal_plan: Filter by chef meal plan ID
    - prep_plan: Filter by prep plan ID
    - status: Filter by status (uploaded, reviewed, reimbursed, rejected)
    - date_from: Filter receipts on or after this date (YYYY-MM-DD)
    - date_to: Filter receipts on or before this date (YYYY-MM-DD)
    - ordering: Sort field (default: -purchase_date)
    - page: Page number
    - page_size: Items per page (default: 20, max: 100)
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    if request.method == 'GET':
        receipts = MealPlanReceipt.objects.filter(chef=chef)
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            receipts = receipts.filter(category=category)
        
        customer_id = request.query_params.get('customer')
        if customer_id:
            receipts = receipts.filter(customer_id=customer_id)
        
        chef_meal_plan_id = request.query_params.get('chef_meal_plan')
        if chef_meal_plan_id:
            receipts = receipts.filter(chef_meal_plan_id=chef_meal_plan_id)
        
        prep_plan_id = request.query_params.get('prep_plan')
        if prep_plan_id:
            receipts = receipts.filter(prep_plan_id=prep_plan_id)
        
        receipt_status = request.query_params.get('status')
        if receipt_status:
            receipts = receipts.filter(status=receipt_status)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            receipts = receipts.filter(purchase_date__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            receipts = receipts.filter(purchase_date__lte=date_to)
        
        # Ordering
        ordering = request.query_params.get('ordering', '-purchase_date')
        valid_orderings = [
            '-purchase_date', 'purchase_date',
            '-amount', 'amount',
            '-created_at', 'created_at'
        ]
        if ordering in valid_orderings:
            receipts = receipts.order_by(ordering, '-id')
        else:
            receipts = receipts.order_by('-purchase_date', '-id')
        
        # Paginate
        paginator = ReceiptPagination()
        page = paginator.paginate_queryset(receipts, request)
        serializer = MealPlanReceiptListSerializer(
            page or receipts, many=True, context={'request': request}
        )
        
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = MealPlanReceiptUploadSerializer(data=request.data)
        if serializer.is_valid():
            # Validate that customer/meal_plan belongs to this chef if provided
            customer = serializer.validated_data.get('customer')
            chef_meal_plan = serializer.validated_data.get('chef_meal_plan')
            prep_plan = serializer.validated_data.get('prep_plan')
            
            # Validate chef_meal_plan ownership
            if chef_meal_plan and chef_meal_plan.chef != chef:
                return Response(
                    {'chef_meal_plan': 'This meal plan does not belong to you.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate prep_plan ownership
            if prep_plan and prep_plan.chef != chef:
                return Response(
                    {'prep_plan': 'This prep plan does not belong to you.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            receipt = serializer.save(chef=chef)
            return Response(
                MealPlanReceiptSerializer(receipt, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def receipt_detail(request, receipt_id):
    """
    GET: Get details of a specific receipt.
    PATCH: Update receipt details (cannot change image once uploaded).
    DELETE: Delete a receipt.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    receipt = get_object_or_404(MealPlanReceipt, id=receipt_id, chef=chef)
    
    if request.method == 'GET':
        serializer = MealPlanReceiptSerializer(receipt, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'PATCH':
        # Only allow updating certain fields
        allowed_fields = [
            'amount', 'currency', 'tax_amount', 'category',
            'merchant_name', 'purchase_date', 'description', 'items',
            'customer', 'chef_meal_plan', 'prep_plan'
        ]
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = MealPlanReceiptUploadSerializer(
            receipt, data=update_data, partial=True
        )
        if serializer.is_valid():
            # Validate ownership of linked objects
            chef_meal_plan = serializer.validated_data.get('chef_meal_plan')
            prep_plan = serializer.validated_data.get('prep_plan')
            
            if chef_meal_plan and chef_meal_plan.chef != chef:
                return Response(
                    {'chef_meal_plan': 'This meal plan does not belong to you.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if prep_plan and prep_plan.chef != chef:
                return Response(
                    {'prep_plan': 'This prep plan does not belong to you.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            receipt = serializer.save()
            return Response(
                MealPlanReceiptSerializer(receipt, context={'request': request}).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        receipt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receipt_stats(request):
    """
    Get receipt statistics for the authenticated chef.
    
    Query parameters:
    - period: 'week', 'month', 'quarter', 'year', 'all' (default: 'month')
    - customer: Filter by customer ID
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    receipts = MealPlanReceipt.objects.filter(chef=chef)
    
    # Period filtering
    period = request.query_params.get('period', 'month')
    today = timezone.now().date()
    
    if period == 'week':
        start_date = today - timedelta(days=7)
        receipts = receipts.filter(purchase_date__gte=start_date)
    elif period == 'month':
        start_date = today - timedelta(days=30)
        receipts = receipts.filter(purchase_date__gte=start_date)
    elif period == 'quarter':
        start_date = today - timedelta(days=90)
        receipts = receipts.filter(purchase_date__gte=start_date)
    elif period == 'year':
        start_date = today - timedelta(days=365)
        receipts = receipts.filter(purchase_date__gte=start_date)
    # 'all' - no date filtering
    
    # Customer filtering
    customer_id = request.query_params.get('customer')
    if customer_id:
        receipts = receipts.filter(customer_id=customer_id)
    
    # Calculate statistics
    total_count = receipts.count()
    total_amount = receipts.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # By category
    by_category = receipts.values('category').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')
    
    # By status
    by_status = receipts.values('status').annotate(
        count=Count('id'),
        total=Sum('amount')
    )
    
    # By customer (top 5)
    by_customer = receipts.exclude(customer__isnull=True).values(
        'customer__id', 'customer__username'
    ).annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')[:5]
    
    # Monthly trend (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_trend = (
        receipts
        .filter(purchase_date__gte=six_months_ago)
        .extra(select={'month': "date_trunc('month', purchase_date)"})
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('month')
    )
    
    return Response({
        'period': period,
        'total_receipts': total_count,
        'total_amount': float(total_amount),
        'currency': 'USD',  # Could be made dynamic
        'by_category': [
            {
                'category': item['category'],
                'count': item['count'],
                'total': float(item['total'] or 0)
            }
            for item in by_category
        ],
        'by_status': {
            item['status']: {
                'count': item['count'],
                'total': float(item['total'] or 0)
            }
            for item in by_status
        },
        'top_customers': [
            {
                'customer_id': item['customer__id'],
                'username': item['customer__username'],
                'count': item['count'],
                'total': float(item['total'] or 0)
            }
            for item in by_customer
        ],
        'monthly_trend': [
            {
                'month': item['month'].isoformat() if item['month'] else None,
                'count': item['count'],
                'total': float(item['total'] or 0)
            }
            for item in monthly_trend
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_receipts(request, customer_id):
    """
    Get all receipts for a specific customer.
    Useful for billing/reimbursement views.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    receipts = MealPlanReceipt.objects.filter(chef=chef, customer_id=customer_id)
    
    # Calculate totals
    totals = receipts.aggregate(
        total_amount=Sum('amount'),
        total_count=Count('id'),
        reimbursed_amount=Sum('amount', filter=Q(status='reimbursed')),
        pending_amount=Sum('amount', filter=Q(status='uploaded'))
    )
    
    # Paginate
    paginator = ReceiptPagination()
    page = paginator.paginate_queryset(receipts.order_by('-purchase_date'), request)
    serializer = MealPlanReceiptListSerializer(
        page or receipts, many=True, context={'request': request}
    )
    
    data = {
        'receipts': serializer.data if page is None else None,
        'totals': {
            'total_amount': float(totals['total_amount'] or 0),
            'total_count': totals['total_count'] or 0,
            'reimbursed_amount': float(totals['reimbursed_amount'] or 0),
            'pending_amount': float(totals['pending_amount'] or 0),
        }
    }
    
    if page is not None:
        response = paginator.get_paginated_response(serializer.data)
        response.data['totals'] = data['totals']
        return response
    
    return Response(data)





