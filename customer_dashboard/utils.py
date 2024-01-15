from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import GoalTrackingSerializer, ChatThreadSerializer
from .models import GoalTracking, ChatThread
from custom_auth.serializers import CustomUserSerializer, AddressSerializer
from custom_auth.models import Address, UserRole
from meals.serializers import MealPlanSerializer, OrderSerializer
from meals.models import MealPlan, Order
from .permissions import IsCustomer
from django.utils import timezone
from django.contrib.auth import get_user_model
from custom_auth.models import CustomUser

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_adjust_week_shift(request):
    # Deserialize the request data
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    serializer = CustomUserSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    week_shift_increment = serializer.validated_data.get('week_shift_increment')

    user = CustomUser.objects.get(id=request.user.id)
    user = user
    # Update the user's week shift, ensuring it doesn't go below 0
    new_week_shift = user.week_shift + week_shift_increment
    if new_week_shift < 0:
        return Response({'status': 'error', 'message': 'Week shift cannot be negative.'}, status=400)
    else:
        user.week_shift = new_week_shift
        user.save()


    return Response({
        'status': 'success',
        'message': f'Week shift adjusted to {new_week_shift} weeks.',
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_adjust_current_week(request):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Reset the user's week shift to 0
    user.week_shift = 0
    user.save()

    return Response({
        'status': 'success',
        'message': 'Week shift reset to the current week.',
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_update_goal(request):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    serializer = GoalTrackingSerializer(data=request.data)
    if serializer.is_valid():
        goal, created = GoalTracking.objects.get_or_create(user=user)
        goal.goal_name = serializer.validated_data.get('goal_name', goal.goal_name)
        goal.goal_description = serializer.validated_data.get('goal_description', goal.goal_description)
        goal.save()
        return Response({
            'status': 'success',
            'message': 'Goal updated successfully.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_get_goal(request):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    try:
        goal = user.goal
        serializer = GoalTrackingSerializer(goal)
        return Response({
            'status': 'success',
            'goal': serializer.data,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except GoalTracking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Goal not found.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_get_user_info(request):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        if request.data.get('user_id') != user.id:
            return {'status': 'error', 'message': "Unauthorized access.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        address = Address.objects.get(user=user)
        user_serializer = CustomUserSerializer(user)
        address_serializer = AddressSerializer(address)
        
        user_info = user_serializer.data
        user_info.update({'postal_code': address_serializer.data.get('postalcode')})

        return Response({'status': 'success', 'user_info': user_info})
    except get_user_model().DoesNotExist:
        return Response({'status': 'error', 'message': 'User not found.'}, status=404)
    except Address.DoesNotExist:
        return Response({'status': 'error', 'message': 'Address not found for user.'}, status=404)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_access_past_orders(request):
    user_id = request.data.get('user_id')
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Find meal plans within the week range with specific order statuses
    meal_plans = MealPlan.objects.filter(
        user_id=user_id,
        order__status__in=['Completed', 'Cancelled', 'Refunded']
    )

    if not meal_plans.exists():
        return Response({
            'status': 'info', 
            'message': "No meal plans found for the current week.", 
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    # Retrieve orders associated with the meal plans
    orders = Order.objects.filter(meal_plan__in=meal_plans)

    # Serialize the orders
    serialized_orders = OrderSerializer(orders, many=True)

    return Response({
        'orders': serialized_orders.data, 
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    })

