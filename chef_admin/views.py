from django.shortcuts import render
from custom_auth.models import UserRole
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from meals.models import Order, Dish, Meal
from django.db.models import Count, Sum
from django.utils import timezone
from django.db.models.functions import TruncWeek
from django.db.models import F
from datetime import datetime
from django.http import HttpResponse



def is_chef(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'chef'
        except UserRole.DoesNotExist:
            return False
    return False


@login_required
@user_passes_test(is_chef)
def chef_dashboard(request):
    # Fetch orders related to this chef
    orders = Order.objects.filter(meals__chef=request.user.chef)
    return render(request, 'chef_admin/dashboard.html', {'orders': orders})


@login_required
@user_passes_test(is_chef)
def order_dashboard(request):
    # Fetch orders related to this chef
    orders = Order.objects.filter(meals__chef=request.user.chef)
    return render(request, 'chef_admin/orders.html', {'orders': orders})


# @login_required
# @user_passes_test(is_chef)
# def most_popular_dishes(request):
#     start_date_str = request.GET.get('start_date', None)
#     end_date_str = request.GET.get('end_date', None)

#     if start_date_str and end_date_str:
#         start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
#         end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
#     else:
#         today = timezone.now().date()
#         start_date = today - timezone.timedelta(days=6)
#         end_date = today

#     dishes = Dish.objects.filter(
#         chef=request.user.chef,
#         meal__ordermeal__order__status='Completed',
#         meal__ordermeal__order__order_date__range=[start_date, end_date]
#     ).annotate(order_count=Count('meal__ordermeal'))

#     data = [{"name": dish.name, "count": dish.order_count} for dish in dishes]
#     return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_chef)
def sales_over_time(request):
    start_date_str = request.GET.get('start_date', None)
    end_date_str = request.GET.get('end_date', None)
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        today = timezone.now().date()
        start_date = today - timezone.timedelta(days=30)
        end_date = today
    
    orders_within_date_range = Order.objects.filter(
        meals__chef=request.user.chef,
        order_date__gte=start_date,
        order_date__lte=end_date,
        status='Completed'
    )
    
    weekly_sales = orders_within_date_range.annotate(
        week=TruncWeek('order_date')
    ).annotate(
        sales=Sum(F('ordermeal__meal__price') * F('ordermeal__quantity'))
    ).values('week', 'sales').order_by('week')
    
    data = [{"week": str(week_data['week']), "sales": week_data['sales']} for week_data in weekly_sales]
    
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_chef)
def incomplete_orders(request):
    start_date_str = request.GET.get('start_date', None)
    end_date_str = request.GET.get('end_date', None)
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        today = timezone.now().date()
        start_date = today - timezone.timedelta(days=30)
        end_date = today

    orders_within_date_range = Order.objects.filter(
        meals__chef=request.user.chef,
        order_date__gte=start_date,
        order_date__lte=end_date,
        status__in=['Cancelled', 'Refunded', 'Delayed']
    )
    
    orders = orders_within_date_range.values('status').annotate(total=Count('id'))
    
    data = [{"status": order['status'], "total": order['total']} for order in orders]
    
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_chef)
def active_orders(request):
    active_orders = Order.objects.filter(
        meals__chef=request.user.chef,
        status__in=['Placed', 'In Progress']
    ).values(
        'id',
        'customer__username',
        'order_date',
        'special_requests',
        'status'
    )
    
    data = list(active_orders)
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(is_chef)
def all_orders(request):
    all_orders = Order.objects.filter(
        meals__chef=request.user.chef,
        status__in=['Placed', 'In Progress', 'Completed', 'Cancelled', 'Refunded', 'Delayed']
    ).values(
        'id',
        'customer__username',
        'order_date',
        'special_requests',
        'status'
    )
    
    data = list(all_orders)
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(is_chef)
def update_order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id, meals__chef=request.user.chef)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    if request.method == 'POST':
        new_status = request.POST.get('new_status')
        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            order.status = new_status
            order.save()
            return JsonResponse({"message": "Order status updated"}, status=200)
        else:
            return JsonResponse({"error": "Invalid status"}, status=400)


