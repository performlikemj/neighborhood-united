import logging
import os
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import date, datetime, timedelta
from .forms import DishForm, IngredientForm, MealForm
from .models import Meal, Cart, Dish, Ingredient, Order, OrderMeal, MealPlan, MealPlanMeal, Instruction
from django.http import JsonResponse, HttpResponseBadRequest
from .serializers import MealPlanSerializer
from chefs.models import Chef
from django.conf import settings
import requests
from django.http import JsonResponse
from rest_framework.response import Response
from django.urls import reverse
from django.http import HttpResponseBadRequest
from custom_auth.models import Address, CustomUser
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseForbidden
from custom_auth.models import UserRole
import json
from django.utils import timezone
from django.contrib import messages
import stripe
from openai import OpenAI
from django.views.decorators.http import require_http_methods
from customer_dashboard.models import GoalTracking, ChatThread, UserHealthMetrics, CalorieIntake
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from customer_dashboard.permissions import IsCustomer
from django.http import JsonResponse
from django.http import HttpResponseForbidden


logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

stripe.api_key = settings.STRIPE_SECRET_KEY

def is_chef(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'chef'
        except UserRole.DoesNotExist:
            return False
    return False

def is_customer(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'customer'
        except UserRole.DoesNotExist:
            return False
    return False

def api_search_ingredients(request):
    query = request.GET.get('query', '')
    results = search_ingredients(query)
    return JsonResponse(results)


def search_ingredients(query, number=20, apiKey=settings.SPOONACULAR_API_KEY):
    search_url = "https://api.spoonacular.com/food/ingredients/search"
    search_params = {
        "query": query,
        "number": number,
        "apiKey": apiKey,
    }
    response = requests.get(search_url, params=search_params)
    response.raise_for_status()  # Raises an HTTPError if the response status isn't 200
    return response.json()

def get_ingredient_info(id, apiKey=settings.SPOONACULAR_API_KEY):
    info_url = f"https://api.spoonacular.com/food/ingredients/{id}/information"
    info_params = {
        "amount": 1,
        "apiKey": apiKey,
    }
    response = requests.get(info_url, params=info_params)
    response.raise_for_status()  # Raises an HTTPError if the response status isn't 200
    return response.json()

@user_passes_test(is_chef, login_url='custom_auth:login')
def api_create_ingredient(request):
    if request.method == 'POST':
        chef = request.user.chef
        name = request.POST.get('name')
        spoonacular_id = request.POST.get('spoonacular_id')
        if chef.ingredients.filter(spoonacular_id=spoonacular_id).exists():
            # Ingredient already exists, no need to add it again
            return JsonResponse({"message": "Ingredient already added"}, status=400)
        
        # Get ingredient info from Spoonacular API
        ingredient_info = get_ingredient_info(spoonacular_id)
        calories = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Calories'), None)
        ingredient = Ingredient.objects.create(name=name, spoonacular_id=spoonacular_id, chef_id=chef.id, calories=calories)
        # Write to file
        with open('ingredients.txt', 'a') as f:
            f.write(f'{name}: {calories}\n')

        client = OpenAI(api_key=settings.OPENAI_KEY)
        # Delete old file from OpenAI
        try:
            with open('ingredients_current_file_id.txt', 'r') as f:
                old_file_id = f.read().strip()
            client.beta.assistants.delete(old_file_id)
            with open('ingredients_old_file_id.txt', 'a') as f:
                f.write(f'{old_file_id}\n')
        except FileNotFoundError:
            pass  # If 'ingredients_current_file_id.txt' doesn't exist, there's no old file to delete

        # Upload file to OpenAI
        file = client.files.create(
            file=open("ingredients.txt", "rb"),
            purpose='assistants'
        )

        # Write new file id to 'ingredients_current_file_id.txt'
        with open('ingredients_current_file_id.txt', 'w') as f:
            f.write(file.id)

        return JsonResponse({
            'name': ingredient.name,
            'spoonacular_id': ingredient.spoonacular_id,
            'calories': ingredient.calories,
            'message': "Ingredient created successfully"
        })

@login_required
def add_to_cart(request, meal_id):
    meal = get_object_or_404(Meal, pk=meal_id)
    user_home_postal_code = request.user.address.postalcode

    if meal.chef.address.postalcode != user_home_postal_code:
        return HttpResponseBadRequest('Chef does not serve your area.')

    if not request.user.email_confirmed:
        return redirect('shared:verify_email')
    
    if not meal.is_available():
        return HttpResponseBadRequest('This meal is no longer available.')

    cart, created = Cart.objects.get_or_create(customer=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, meal=meal, defaults={'quantity': 1})
    if not created:
        cart_item.save()
    cart.save()

    return redirect('meals:cart_view')


@login_required
def cart_view(request):
    cart = get_object_or_404(Cart, customer=request.user)
    total_price = sum(meal.price for meal in cart.meals.all())

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('meals:cart_view'), 'name': 'Cart'},
    ]

    context = {
        'cart': cart,
        'total_price': total_price,
        'breadcrumbs': breadcrumbs,
    }

    return render(request, 'meals/cart_view.html', context)

@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, customer=request.user)
    if request.method == 'POST':
        delivery_method = request.POST.get('delivery_method')
        default_address = Address.objects.filter(user=request.user).first()

        # Create the Order instance and set the status and delivery_method
        order = Order.objects.create(
            customer=request.user,
            status='Placed',
            delivery_method=delivery_method,
            address=default_address if delivery_method == 'Delivery' else None,
            meal_plan=cart.meal_plan  # associate the MealPlan with the Order
        )
        # Transfer items from cart to the order
        for meal in cart.meals.all():
            # Optional: Update inventory, decrement the available quantity
            # meal.available_quantity -= 1
            # meal.save()
            OrderMeal.objects.create(order=order, meal=meal, quantity=1)

        # Empty the cart
        cart.meals.clear()
        cart.save()

        return redirect('meals:order_confirmation')

    return render(request, 'meals/checkout.html', {'cart': cart})


@login_required
def order_confirmation(request):
    # Fetch the latest order placed by the user
    latest_order = Order.objects.filter(customer=request.user).latest('id')
    
    context = {
        'order': latest_order,
    }
    
    return render(request, 'meals/order_confirmation.html', context)



@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # Ensure the order belongs to the requesting user
    if order.customer != request.user:
        return HttpResponseForbidden("You do not have permission to view this order.")

    # Get the related MealPlanMeals if the order has an associated MealPlan
    meal_plan_meals = None
    if order.meal_plan:
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=order.meal_plan).order_by('day', 'meal')

    context = {
        'order': order,
        'meal_plan_meals': meal_plan_meals,
    }

    return render(request, 'meals/order_details.html', context)


def dish_list(request):
    chefs = Chef.objects.all()
    # Here you are getting all the dishes, not just the ones associated with the chefs
    dishes = Dish.objects.all()
    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('meals:dish_list'), 'name': 'Dishes'},
    ]

    context = {
        'chefs': chefs,
        'dishes': dishes,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'meals/dish_list.html', context)


def dish_detail(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id)

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('meals:dish_list'), 'name': 'Dishes'},
        {'url': reverse('meals:dish_detail', args=[dish_id]), 'name': dish.name},
    ]

    context = {
        'dish': dish,
        'chef': dish.chef,  
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'meals/dish_detail.html', context)


@user_passes_test(is_chef, login_url='custom_auth:login')
def create_dish(request):
    if request.method == 'POST':
        form = DishForm(request.POST)
        if form.is_valid():
            dish = form.save(commit=False)
            dish.chef = request.user.chef
            dish.save()
            form.save_m2m()
            return redirect('meals:dish_detail', dish_id=dish.id)

    else:
        form = DishForm()
    context = {'form': form}
    return render(request, 'meals/create_dish.html', context)

@user_passes_test(is_chef, login_url='custom_auth:login')
def update_dish(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id)

    # Ensure the dish belongs to the authenticated chef
    if dish.chef != request.user.chef:
        return redirect('error_page')

    if request.method == 'POST':
        form = DishForm(request.POST, instance=dish)
        if form.is_valid():
            form.save()
            return redirect('meals:dish_detail', dish_id=dish.id)
    else:
        form = DishForm(instance=dish)

    context = {'form': form, 'dish': dish}
    return render(request, 'meals/update_dish.html', context)


@user_passes_test(is_chef, login_url='custom_auth:login')
def create_ingredient(request):
    if request.method == 'POST':
        # I don't believe this does anything except add to template, because functionality is in api_create_ingredient
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save(commit=False)
            spoonacular_id = form.cleaned_data.get('spoonacular_id')
            if spoonacular_id:
                # Check if ingredient already exists for this chef
                chef = request.user.chef
                if chef.ingredients.filter(spoonacular_id=spoonacular_id).exists():
                    # Ingredient already exists, no need to add it again
                    return JsonResponse({"message": "Ingredient already added"}, status=400)

                ingredient.spoonacular_id = spoonacular_id
                ingredient.chef = chef
                try:
                    ingredient.save()
                except Exception as e:
                    return JsonResponse({"message": str(e)}, status=400)
                return JsonResponse({"message": "Ingredient created successfully"}, status=200)
            else:
                return JsonResponse({"message": "No Spoonacular ID found"}, status=400)
    else:
        form = IngredientForm()
    ingredients = Ingredient.objects.filter(chef=request.user.chef)
    context = {'form': form, 'ingredients': ingredients}
    return render(request, 'meals/create_ingredient.html', context)


@login_required
@user_passes_test(is_chef, login_url='custom_auth:login')
def create_meal(request):
    if request.method == 'POST':
        form = MealForm(request.POST)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.chef = request.user.chef
            
            # Check for existing meals by this chef that have the same date range
            existing_meal = Meal.objects.filter(
                chef=meal.chef,
                start_date=meal.start_date,
            ).first()
            
            if existing_meal:
                # Handle the logic for adding different party sizes to the existing meal
                # You might redirect to an 'update meal' view or something similar
                pass
            else:
                meal.save()
                form.save_m2m()
                return redirect('meals:meal_detail', meal_id=meal.id)
    else:
        form = MealForm()
    context = {'form': form}
    return render(request, 'meals/create_meal.html', context)


def chef_weekly_meal(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)
    # Calculate the current week's date range
    week_shift = max(int(request.user.week_shift), 0)
    today = timezone.now().date() + timedelta(weeks=week_shift)
    meals = chef.meals.filter(start_date__gte=today).order_by('start_date')

    context = {
        'chef': chef,
        'meals': meals,
    }
    return render(request, 'meals/chef_weekly_meal.html', context)

def meal_detail(request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)
    summary = meal.review_summary

    context = {
        'meal': meal,
        'summary': summary,
    }
    return render(request, 'meals/meal_detail.html', context)


def get_meal_details(request):
    meal_id = request.GET.get('meal_id')
    if not meal_id:
        return JsonResponse({"error": "Meal ID is required."}, status=400)

    meal = get_object_or_404(Meal, id=meal_id)

    meal_details = {
        "meal_id": meal.id,
        "name": meal.name,
        "chef": meal.chef.user.username,
        "start_date": meal.start_date.strftime('%Y-%m-%d'),
        "is_available": meal.is_available(request.user.week_shift), 
        "dishes": [dish.name for dish in meal.dishes.all()]
    }

    # Optional: Find the day of the meal in the meal plan, if needed
    meal_plan_meal = MealPlanMeal.objects.filter(meal=meal).first()
    if meal_plan_meal:
        meal_details["day"] = meal_plan_meal.day

    return JsonResponse(meal_details)

def meal_list(request):
    meals = Meal.objects.all()

    context = {
        'meals': meals,
    }
    return render(request, 'meals/meal_list.html', context)


def meals_with_dish(request, dish_id):
    meals = Meal.objects.filter(dishes__id=dish_id)

    context = {
        'meals': meals,
    }
    return render(request, 'meals/meals_with_dish.html', context)


@login_required
def view_past_orders(request):
    past_orders = Order.objects.filter(customer=request.user).order_by('-order_date')
    
    return render(request, 'meals/view_past_orders.html', {'past_orders': past_orders})


@login_required
def create_meal_plan(request):
    pass
    # if request.method == 'POST':
    #     user = request.user
    #     week_start_date = request.POST.get('week_start_date')
    #     week_end_date = request.POST.get('week_end_date')
    #     selected_meals = request.POST.getlist('selected_meals')  # Assuming this is a list of meal ids

    #     # Create MealPlan
    #     meal_plan, created = MealPlan.objects.get_or_create(user=user, week_start_date=week_start_date, week_end_date=week_end_date)

    #     # Add Meals to MealPlan
    #     for meal_id in selected_meals:
    #         meal = get_object_or_404(Meal, id=meal_id)
    #         day = request.POST.get(f'day_for_meal_{meal_id}')  # Assuming you pass the day for each meal
    #         MealPlanMeal.objects.create(meal_plan=meal_plan, meal=meal, day=day)

    #     return redirect('meal_plan_confirmation_view')  # Replace with your confirmation view

    # return HttpResponseBadRequest('Invalid Method')


@login_required
@require_http_methods(["GET", "POST"])  # Restrict to GET and POST methods
def api_customize_meal_plan(request, meal_plan_id):
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)

    if request.method == 'POST':
        # Handle AJAX requests for meal plan modifications
        if request.is_ajax():
            data = json.loads(request.body)
            action = data.get('action')
            meal_id = data.get('meal_id')
            day = data.get('day')

            if action == 'remove':
                MealPlanMeal.objects.filter(meal_plan=meal_plan, meal__id=meal_id, day=day).delete()
                return JsonResponse({'status': 'success', 'action': 'removed'})

            elif action == 'replace':
                new_meal_id = data.get('new_meal_id')
                new_meal = get_object_or_404(Meal, id=new_meal_id)
                MealPlanMeal.objects.filter(meal_plan=meal_plan, meal__id=meal_id, day=day).update(meal=new_meal)
                return JsonResponse({'status': 'success', 'action': 'replaced', 'new_meal': new_meal.name})

            elif action == 'add':
                new_meal_id = data.get('new_meal_id')
                new_meal = get_object_or_404(Meal, id=new_meal_id)
                MealPlanMeal.objects.create(meal_plan=meal_plan, meal=new_meal, day=day)
                return JsonResponse({'status': 'success', 'action': 'added', 'new_meal': new_meal.name})

            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        # Render the customization form or UI for GET requests
        else:
            return render(request, 'customize_meal_plan.html', {'meal_plan': meal_plan})

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required
@user_passes_test(is_customer, login_url='custom_auth:profile')
def get_alternative_meals(request):

    # Calculate the current week's date range
    week_shift = max(int(request.user.week_shift), 0)
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    # Get current day from the request
    current_day = request.GET.get('day', adjusted_today.strftime('%A'))
    # Convert DAYS_OF_WEEK to a list of day names
    days_of_week_list = [day[0] for day in MealPlanMeal.DAYS_OF_WEEK]

    # Convert the day name to a date object
    current_day_date = start_of_week + timedelta(days=days_of_week_list.index(current_day))
    # Retrieve the meal plan for the specified week
    meal_plan = MealPlan.objects.filter(
        user=request.user,
        week_start_date=start_of_week,
        week_end_date=end_of_week
    ).first()

    if not meal_plan:
        return JsonResponse({"message": "No meal plan found for the specified week."})

    # Query MealPlanMeal for the specific day within the meal plan
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=current_day)

    # Query meals based on postal code, and availability for the specific day
    postal_query = Meal.postal_objects.for_user(user=request.user).filter(start_date=current_day_date)
    # Apply dietary preference filter only if it's not None
    meals = postal_query.filter(id__in=Meal.dietary_objects.for_user(request.user))

    # Return the meals as JSON
    if meals.exists():
        meals_data = [{
            'id': meal.id,
            'name': meal.name,
            'chef': meal.chef.user.username,
            # ... include other meal details as needed ...
        } for meal in meals]
        return JsonResponse({"success": True, "meals": meals_data})
    else:
        return JsonResponse({"success": False, "message": "No alternative meals available."})



@login_required
@user_passes_test(is_customer, login_url='custom_auth:profile')
@require_http_methods(["POST"])
def submit_meal_plan_updates(request):
    try:
        # Load the JSON data from the request
        data = json.loads(request.body)
        updated_meals = data.get('mealPlan')

        # Assuming each meal in updated_meals includes a 'meal_plan_id'
        if not updated_meals:
            raise ValueError("Updated meal plan is empty.")

        # Example: getting the meal_plan_id from the first meal
        meal_plan_id = updated_meals[0].get('meal_plan_id')
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)

        # Clear existing MealPlanMeal entries
        MealPlanMeal.objects.filter(meal_plan=meal_plan).delete()

        # Create new MealPlanMeal entries based on the updated meal plan
        for meal in updated_meals:
            MealPlanMeal.objects.create(
                meal_plan=meal_plan,
                meal_id=meal['meal_id'],
                day=meal['day']
            )

        return JsonResponse({'status': 'success', 'message': 'Meal plan updated successfully.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def meal_plan_approval(request):
    # Step 1: Retrieve the current MealPlan for the user
    week_shift = max(int(request.user.week_shift), 0)
    today = timezone.now().date() + timedelta(weeks=week_shift)
    meal_plan = get_object_or_404(MealPlan, user=request.user, week_start_date__lte=today, week_end_date__gte=today)
    
    # Check if the meal plan is already associated with an order
    if meal_plan.order:
        if meal_plan.order.is_paid:
            # If the order is paid, redirect to the confirmation page
            messages.info(request, 'This meal plan has already been paid for.')
            return redirect('meals:meal_plan_confirmed')
        else:
            # If the order is not paid, redirect to the payment page
            messages.info(request, 'This meal plan has an unpaid order. Please complete the payment.')
            return redirect('meals:process_payment', order_id=meal_plan.order.id)

    # Step 2: Display it for approval
    if request.method == 'POST':
        # Step 3: Handle meal plan approval
        # Create an Order object
        order = Order(customer=request.user)
        order.save()  # Save the order to generate an ID
        
        # Step 5: Create OrderMeal objects for each meal in the meal plan
        for meal in meal_plan.meal.all():
            OrderMeal.objects.create(order=order, meal=meal, quantity=1)

        # Step 4: Link the Order to the MealPlan
        meal_plan.order = order
        meal_plan.save()


        # Step 6: Redirect to payment
        return redirect('meals:process_payment', order_id=order.id)
    
    # Render the meal plan approval page
    return render(request, 'meals/approve_meal_plan.html', {'meal_plan': meal_plan})

@login_required
def process_payment(request, order_id):
    # Get the order object
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    if request.method == 'POST':
        try:
            charge = stripe.Charge.create(
                amount=int(order.total_price() * 100),  # amount in cents
                currency='usd',
                description=f'Order {order.id}',
                source=request.POST['stripeToken']
            )
            if charge.paid:
                order.is_paid = True
                order.status = 'Completed'
                order.save()

            # After the order is marked as completed, process each meal in the order
            for order_meal in order.ordermeal_set.all():
                meal = order_meal.meal
                # Assuming meal_name, meal_description, and portion_size are attributes of Meal
                CalorieIntake.objects.create(
                    user=request.user,
                    meal_name=meal.name,  # Replace with actual attribute names
                    meal_description=meal.description,
                    portion_size="1",  # Ensure this info is available
                    date_recorded=timezone.now()
                )
                messages.success(request, 'Your payment was successful.')
                return redirect('meals:meal_plan_confirmed')
            else:
                messages.error(request, 'Your payment was unsuccessful. Please try again.')
                return redirect('meals:process_payment', order_id=order.id)

        except stripe.error.CardError as e:
            # The card has been declined
            body = e.json_body
            err = body.get('error', {})
            messages.error(request, f"An error occurred: {err.get('message')}")
            return redirect('meals:process_payment', order_id=order.id)

    # Render the payment page
    return render(request, 'meals/payment.html', {'order': order, 'stripe_public_key': settings.STRIPE_PUBLIC_KEY})



@login_required
def meal_plan_confirmed(request):
    # Get the most recent paid order for the user
    order = Order.objects.filter(customer=request.user, is_paid=True).latest('order_date')

    # Render a confirmation page after the meal plan has been paid for
    return render(request, 'meals/meal_plan_confirmed.html', {'order': order})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_meal_plans(request):
    try:
        user = request.user
        week_start_date_str = request.query_params.get('week_start_date')
        if week_start_date_str:
            week_start_date = datetime.strptime(week_start_date_str, '%Y-%m-%d').date()
            meal_plans = MealPlan.objects.filter(user=user, week_start_date=week_start_date)
        else:
            meal_plans = MealPlan.objects.filter(user=user)

        serializer = MealPlanSerializer(meal_plans, many=True)
        return Response(serializer.data, status=200)
    
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_generate_cooking_instructions(request):
    try:
        from .tasks import generate_instructions
        # Extract meal_plan_meal_ids from request data
        meal_plan_meal_ids = request.data.get('meal_plan_meal_ids', [])
        if not meal_plan_meal_ids:
            return Response({"error": "meal_plan_meal_ids are required"}, status=400)

        # Verify that each MealPlanMeal exists and belongs to the current user
        valid_meal_plan_meal_ids = []
        for meal_plan_meal_id in meal_plan_meal_ids:
            try:
                meal_plan_meal = MealPlanMeal.objects.get(id=meal_plan_meal_id)
                valid_meal_plan_meal_ids.append(meal_plan_meal.id)  # Append the ID, not the MealPlanMeal instance
            except MealPlanMeal.DoesNotExist:
                logger.warning(f"MealPlanMeal with ID {meal_plan_meal_id} not found or unauthorized access attempted.")
                continue

        if not valid_meal_plan_meal_ids:
            return Response({"error": "No valid meal plan meals found or you do not have permission to access them."}, status=404)

        # Call the Celery task to generate cooking instructions for each valid meal plan meal
        for meal_plan_meal_id in valid_meal_plan_meal_ids:
            print(f'MealPlanMeal id in generation view: {meal_plan_meal_id}')
            generate_instructions.delay(meal_plan_meal_id)

        return Response({"message": "Cooking instructions generation initiated successfully for the selected meal plan meals."}, status=200)

    except Exception as e:
        logger.error(f"An error occurred while initiating cooking instructions generation: {str(e)}")
        return Response({"error": "An unexpected error occurred. Please try again later."}, status=500)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_fetch_instructions(request):
    meal_plan_meal_ids = request.query_params.getlist('meal_plan_meal_ids')
    print(f'Meal plan meal ids: {meal_plan_meal_ids}')
    if not meal_plan_meal_ids:
        return Response({"error": "meal_plan_meal_ids are required"}, status=400)

    instructions = []

    meal_plan_meal_ids = [int(id) for id in meal_plan_meal_ids[0].split(',')]

    for meal_plan_meal_id in meal_plan_meal_ids:
        meal_plan_meal = get_object_or_404(MealPlanMeal, id=meal_plan_meal_id)
        instruction = Instruction.objects.filter(meal_plan_meal=meal_plan_meal).first()
        
        if instruction:
            print(f"Fetched instruction content: {instruction.content}")
            instructions.append({
                "meal_plan_meal_id": meal_plan_meal_id,
                "instructions": instruction.content
            })
        else:
            instructions.append({
                "meal_plan_meal_id": meal_plan_meal_id,
                "instructions": None
            })

    return Response({"instructions": instructions}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_approve_meal_plan(request):
    from shared.utils import approve_meal_plan
    # Extract the user_id and meal_plan_id from the request data
    user_id = request.data.get('user_id')
    meal_plan_id = request.data.get('meal_plan_id')
    
    if not user_id or not meal_plan_id:
        return Response({"status": "error", "message": "user_id and meal_plan_id are required."}, status=400)

    # Call the approve_meal_plan function with the extracted IDs
    result = approve_meal_plan(request, meal_plan_id)

    # Return the result of the approval process
    return Response(result)