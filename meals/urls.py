from django.urls import path, include
from . import views
from . import chef_meals_views
from rest_framework.routers import DefaultRouter

app_name = 'meals'


urlpatterns = [
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
    
    # Stripe onboarding return and refresh URLs
    path('stripe-return/<str:account_id>/', chef_meals_views.stripe_return, name='stripe_return'),
    path('stripe-refresh/<str:account_id>/', chef_meals_views.stripe_refresh, name='stripe_refresh'),
    
    # Existing API URLs
    path('api/search_ingredients/', views.api_search_ingredients, name='api_search_ingredients'),
    path('api/create_ingredient/', views.api_create_ingredient, name='api_create_ingredient'),
    path('api/customize_meal/', views.api_customize_meal_plan, name='api_customize_meal'),
    path('api/submit_meal_plan/', views.submit_meal_plan_updates, name='submit_meal_plan_updates'),
    path('api/meal_plans/', views.api_get_meal_plans, name='api_get_meal_plans'),
    path('api/meal_plans/<int:meal_plan_id>/', views.api_get_meal_plan_by_id, name='api_get_meal_plan_by_id'),
    path('api/meal_plans/<int:meal_plan_id>/stream/', views.api_stream_meal_plan_detail, name='api_stream_meal_plan_detail'),
    path('api/generate_cooking_instructions/', views.api_generate_cooking_instructions, name='api_generate_cooking_instructions'),
    path('api/fetch_instructions/', views.api_fetch_instructions, name='api_fetch_instructions'),
    path('api/approve_meal_plan/', views.api_approve_meal_plan, name='api_approve_meal_plan'),
    path('api/email_approved_meal_plan/', views.api_email_approved_meal_plan, name='api_email_approved_meal_plan'),
    path('api/remove_meal_from_plan/', views.api_remove_meal_from_plan, name='api_remove_meal_from_plan'),
    path('api/replace_meal_plan_meal/', views.api_replace_meal_plan_meal, name='api_replace_meal_plan_meal'),
    path('api/add_meal_slot/', views.api_add_meal_slot, name='api_add_meal_slot'),
    path('api/suggest_alternatives_for_slot/', views.api_suggest_alternatives_for_slot, name='api_suggest_alternatives_for_slot'),
    path('api/fill_meal_slot/', views.api_fill_meal_slot, name='api_fill_meal_slot'),
    path('api/update_meals_with_prompt/', views.api_update_meals_with_prompt, name='api_update_meals_with_prompt'),
    path('api/suggest_meal_alternatives/', views.api_suggest_meal_alternatives, name='api_suggest_meal_alternatives'),
    path('api/generate_meal_plan/', views.api_generate_meal_plan, name='api_generate_meal_plan'),
    path('api/meal_plan_status/<str:task_id>/', views.api_meal_plan_status, name='api_meal_plan_status'),
    path('api/modify_meal_plan/<int:meal_plan_id>/', views.api_modify_meal_plan, name='api_modify_meal_plan'),
    path('api/meal_plans/stream', views.api_stream_meal_plan_generation, name='api_stream_meal_plan_generation'),
    
    # Function-based API views for chef meal orders
    path('api/chef-meal-orders/', chef_meals_views.api_chef_meal_orders, name='api_chef_meal_orders'),
    path('api/chef-meal-orders/<int:order_id>/', chef_meals_views.api_chef_meal_order_detail, name='api_chef_meal_order_detail'),
    path('api/chef-meal-orders/<int:order_id>/cancel/', chef_meals_views.api_cancel_chef_meal_order, name='api_cancel_chef_meal_order'),
    path('api/chef-meal-orders/<int:order_id>/confirm/', chef_meals_views.api_confirm_chef_meal_order, name='api_confirm_chef_meal_order'),
    
    # New API endpoints for the updated chef meal order flow
    path('api/chef-meal-events/<int:event_id>/order/', chef_meals_views.api_create_chef_meal_order, name='api_create_chef_meal_order'),
    path('api/chef-meal-orders/<int:order_id>/adjust-quantity/', chef_meals_views.api_adjust_chef_meal_quantity, name='api_adjust_chef_meal_quantity'),
    
    path('api/debug/order/<int:order_id>/', chef_meals_views.api_debug_order_info, name='api_debug_order_info'),
    
    # New API endpoints for chef meals
    path('api/chef-dashboard-stats/', chef_meals_views.api_chef_dashboard_stats, name='api_chef_dashboard_stats'),
    path('api/stripe-account-status/', views.api_stripe_account_status, name='api_stripe_account_status'),
    path('api/stripe-account-link/', views.api_create_stripe_account_link, name='api_create_stripe_account_link'),
    path('api/bank-account-guidance/', views.api_get_bank_account_guidance, name='api_get_bank_account_guidance'),
    path('api/regenerate-stripe-link/', views.api_regenerate_stripe_account_link, name='api_regenerate_stripe_account_link'),
    path('api/fix-restricted-account/', views.api_fix_restricted_stripe_account, name='api_fix_restricted_stripe_account'),
    path('api/process-chef-meal-payment/<int:order_id>/', views.api_process_chef_meal_payment, name='api_process_chef_meal_payment'),
    path('api/order-payment-status/<int:order_id>/', views.api_order_payment_status, name='api_order_payment_status'),
    path('api/process-meal-payment/<int:order_id>/', views.api_process_meal_payment, name='api_process_meal_payment'),
    path('api/resend-payment-link/<int:order_id>/', views.api_resend_payment_link, name='api_resend_payment_link'),
    path('api/chef-received-orders/', views.api_chef_received_orders, name='api_chef_received_orders'),
    path('api/stripe-webhook/', chef_meals_views.stripe_webhook, name='api_stripe_webhook'),

    # DEBUG-only preview for meals email templates (e.g., payment link)
    path('debug/email/payment-link/', views.debug_payment_link_email, name='debug_payment_link_email'),
    
    # Pantry API Endpoints
    path('api/pantry-items/', views.api_pantry_items, name='api_pantry_items'),
    path('api/pantry-items/<int:pk>/', views.api_pantry_item_detail, name='api_pantry_item_detail'),
    path('api/pantry-items/from-audio/', views.api_pantry_item_from_audio, name='api_pantry_item_from_audio'),
    path('api/generate_emergency_supply/', views.api_generate_emergency_plan, name='api_generate_emergency_supply_list'),
    
    # User Profile API Endpoint
    path('api/user-profile/', views.api_get_user_profile, name='api_get_user_profile'),
    
    # Individual Meal API Endpoint
    path('api/meals/', chef_meals_views.api_get_meals, name='api_get_meals'),
    path('api/chef-meals-by-postal-code/', chef_meals_views.api_get_chef_meals_by_postal_code, name='api_get_chef_meals_by_postal_code'),
    path('api/chef/meals/', chef_meals_views.api_create_chef_meal, name='api_create_chef_meal'),
    path('api/meals/<int:meal_id>/', views.api_get_meal_by_id, name='api_get_meal_by_id'),
    path('api/chef/meals/<int:meal_id>/', chef_meals_views.api_chef_meal_detail, name='api_chef_meal_detail'),
    
    # API endpoint for dietary preferences
    path('api/dietary-preferences/', views.api_dietary_preferences, name='api_dietary_preferences'),
    
    # API endpoints for Instacart integration
    path('api/generate-instacart-link/', views.api_generate_instacart_link, name='api_generate_instacart_link'),
    path('api/meal-plans/<int:meal_plan_id>/instacart-url/', views.api_get_instacart_url, name='api_get_instacart_url'),
    
    # API endpoint for dishes
    path('api/dishes/', chef_meals_views.api_get_dishes, name='api_get_dishes'),
    path('api/dishes/<int:dish_id>/', chef_meals_views.api_get_dish_by_id, name='api_get_dish_by_id'),
    path('api/create-chef-dish/', chef_meals_views.api_create_chef_dish, name='api_create_chef_dish'),
    path('api/dishes/<int:dish_id>/update/', chef_meals_views.api_update_chef_dish, name='api_update_chef_dish'),
    path('api/dishes/<int:dish_id>/delete/', chef_meals_views.api_delete_chef_dish, name='api_delete_chef_dish'),
    path('api/ingredients/', chef_meals_views.api_get_ingredients, name='api_get_ingredients'),
    path('api/ingredients/<int:ingredient_id>/', chef_meals_views.api_get_ingredient_by_id, name='api_get_ingredient_by_id'),
    path('api/chef/ingredients/', chef_meals_views.api_create_chef_ingredient, name='api_create_chef_ingredient'),
    path('api/chef/ingredients/<int:ingredient_id>/', chef_meals_views.api_update_chef_ingredient, name='api_update_chef_ingredient'),
    path('api/chef/ingredients/<int:ingredient_id>/delete/', chef_meals_views.api_delete_chef_ingredient, name='api_delete_chef_ingredient'),
    
    # Chef meals endpoints
    path('api/chef/meals/<int:meal_id>/update/', chef_meals_views.api_update_chef_meal, name='api_update_chef_meal'),
    
    # New API endpoints for chef meal events
    path('api/chef-meal-events/', chef_meals_views.api_chef_meal_events, name='api_chef_meal_events'),
    path('api/chef-meal-events/<int:event_id>/update/', chef_meals_views.api_update_chef_meal_event, name='api_update_chef_meal_event'),
    path('api/chef-meal-events/<int:event_id>/cancel/', chef_meals_views.api_cancel_chef_meal_event, name='api_cancel_chef_meal_event'),
    
    # Add this to your urlpatterns list
    # TODO: Update frontend to use this since Streamlit isn't stateful
    path('api/payment/success/', chef_meals_views.payment_success, name='payment_success'),
    path('api/payment/cancelled/', chef_meals_views.payment_cancelled, name='payment_cancelled'),
]
