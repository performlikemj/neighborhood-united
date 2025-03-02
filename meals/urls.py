from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

app_name = 'meals'

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'api/chef-meal-events', views.ChefMealEventViewSet, basename='chef-meal-event')
router.register(r'api/chef-meal-orders', views.ChefMealOrderViewSet, basename='chef-meal-order')
router.register(r'api/chef-meal-reviews', views.ChefMealReviewViewSet, basename='chef-meal-review')

urlpatterns = [
    # Include the router URLs first
    path('', include(router.urls)),
    
    # Existing URLs

    path('embeddings/', views.embeddings_list, name='meal_list'),
    path('approve_meal_plan/', views.meal_plan_approval, name='approve_meal_plan'),
    
    # Keep the template URLs for admin and similar purposes, but they might not be used by Streamlit
    path('chef/meal_events/', views.chef_meal_dashboard, name='chef_meal_dashboard'),
    path('chef/meal_events/create/', views.create_chef_meal_event, name='create_chef_meal_event'),
    path('chef/meal_events/<int:event_id>/edit/', views.edit_chef_meal_event, name='edit_chef_meal_event'),
    path('chef/meal_events/<int:event_id>/cancel/', views.cancel_chef_meal_event, name='cancel_chef_meal_event'),
    path('chef_meals/', views.browse_chef_meals, name='browse_chef_meals'),
    path('chef_meals/<int:event_id>/', views.chef_meal_detail, name='chef_meal_detail'),
    path('chef_meals/<int:event_id>/order/', views.place_chef_meal_order, name='place_chef_meal_order'),
    path('chef_meal_order/<int:order_id>/', views.view_chef_meal_order, name='view_chef_meal_order'),
    path('my_chef_meal_orders/', views.user_chef_meal_orders, name='user_chef_meal_orders'),
    path('chef_meal_order/<int:order_id>/cancel/', views.cancel_chef_meal_order, name='cancel_chef_meal_order'),
    path('chef_meal_order/<int:order_id>/review/', views.review_chef_meal, name='review_chef_meal'),
    
    # Existing API URLs
    path('api/search_ingredients/', views.api_search_ingredients, name='api_search_ingredients'),
    path('api/create_ingredient/', views.api_create_ingredient, name='api_create_ingredient'),
    path('api/customize_meal/', views.api_customize_meal_plan, name='api_customize_meal'),
    path('api/submit_meal_plan/', views.submit_meal_plan_updates, name='submit_meal_plan_updates'),
    path('api/meal_plans/', views.api_get_meal_plans, name='api_get_meal_plans'),
    path('api/meal_plans/<int:meal_plan_id>/', views.api_get_meal_plan_by_id, name='api_get_meal_plan_by_id'),
    path('api/generate_cooking_instructions/', views.api_generate_cooking_instructions, name='api_generate_cooking_instructions'),
    path('api/fetch_instructions/', views.api_fetch_instructions, name='api_fetch_instructions'),
    path('api/approve_meal_plan/', views.api_approve_meal_plan, name='api_approve_meal_plan'),
    path('api/email_approved_meal_plan/', views.api_email_approved_meal_plan, name='api_email_approved_meal_plan'),
    path('api/remove_meal_from_plan/', views.api_remove_meal_from_plan, name='api_remove_meal_from_plan'),
    path('api/update_meals_with_prompt/', views.api_update_meals_with_prompt, name='api_update_meals_with_prompt'),
    path('api/generate_meal_plan/', views.api_generate_meal_plan, name='api_generate_meal_plan'),
    
    # New API endpoints for chef meals
    path('api/chef-dashboard-stats/', views.api_chef_dashboard_stats, name='api_chef_dashboard_stats'),
    path('api/stripe-account-status/', views.api_stripe_account_status, name='api_stripe_account_status'),
    path('api/create-stripe-account-link/', views.api_create_stripe_account_link, name='api_create_stripe_account_link'),
    path('api/process-chef-meal-payment/<int:order_id>/', views.api_process_chef_meal_payment, name='api_process_chef_meal_payment'),
    path('api/process-meal-payment/<int:order_id>/', views.api_process_meal_payment, name='api_process_meal_payment'),
    path('api/stripe-webhook/', views.api_stripe_webhook, name='api_stripe_webhook'),
    
    # Pantry API Endpoints
    path('api/pantry-items/', views.api_pantry_items, name='api_pantry_items'),
    path('api/pantry-items/<int:pk>/', views.api_pantry_item_detail, name='api_pantry_item_detail'),
    path('api/pantry-items/from-audio/', views.api_pantry_item_from_audio, name='api_pantry_item_from_audio'),
    path('api/generate_emergency_supply/', views.api_generate_emergency_plan, name='api_generate_emergency_supply_list'),
    
    # User Profile API Endpoint
    path('api/user-profile/', views.api_get_user_profile, name='api_get_user_profile'),
    
    # Individual Meal API Endpoint
    path('api/meals/<int:meal_id>/', views.api_get_meal_by_id, name='api_get_meal_by_id'),
]

