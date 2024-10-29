from django.urls import path
from . import views

app_name = 'meals'

urlpatterns = [
    path('', views.dish_list, name='dish_list'),
    path('dish/<int:dish_id>/', views.dish_detail, name='dish_detail'),
    path('add_to_cart/<int:meal_id>/', views.add_to_cart, name='add_to_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('order_confirmation/', views.order_confirmation, name='order_confirmation'),
    path('order/<int:order_id>/', views.order_details, name='order_details'),
    path('cart/', views.cart_view, name='cart_view'),
    path('create_dish/', views.create_dish, name='create_dish'),
    path('update_dish/<int:dish_id>/', views.update_dish, name='update_dish'),
    path('create_ingredient/', views.create_ingredient, name='create_ingredient'),
    path('create_meal/', views.create_meal, name='create_meal'),
    path('meal_detail/<int:meal_id>/', views.meal_detail, name='meal_detail'),
    path('meal_list/', views.meal_list, name='meal_list'),
    path('approve_meal_plan/', views.meal_plan_approval, name='approve_meal_plan'),
    path('payment/<int:order_id>/', views.process_payment, name='process_payment'),
    path('meal_plan_confirmation/', views.meal_plan_confirmed, name='meal_plan_confirmed'),
    path('meals_with_dish/<int:dish_id>/', views.meals_with_dish, name='meals_with_dish'),
    path('chef/<int:chef_id>/weekly_meal/', views.chef_weekly_meal, name='chef_weekly_meal'),
    path('api/search_ingredients/', views.api_search_ingredients, name='api_search_ingredients'),
    path('api/create_ingredient/', views.api_create_ingredient, name='api_create_ingredient'),
    path('api/customize_meal/', views.api_customize_meal_plan, name='api_customize_meal'),
    path('api/submit_meal_plan/', views.submit_meal_plan_updates, name='submit_meal_plan_updates'),
    path('api/get_meal_details/', views.get_meal_details, name='get_meal_details'),
    path('api/get_alternative_meals/', views.get_alternative_meals, name='get_alternative_meals'),
    path('view_past_orders/', views.view_past_orders, name='view_past_orders'),
    path('api/meal_plans/', views.api_get_meal_plans, name='api_get_meal_plans'),
    path('api/generate_cooking_instructions/', views.api_generate_cooking_instructions, name='api_generate_cooking_instructions'),
    path('api/fetch_instructions/', views.api_fetch_instructions, name='api_fetch_instructions'),
    path('api/approve_meal_plan/', views.api_approve_meal_plan, name='api_approve_meal_plan'),
    path('api/email_approved_meal_plan/', views.api_email_approved_meal_plan, name='api_email_approved_meal_plan'),
    # Pantry API Endpoints
    path('api/pantry-items/', views.api_pantry_items, name='api_pantry_items'),
    path('api/pantry-items/<int:pk>/', views.api_pantry_item_detail, name='api_pantry_item_detail'),
]