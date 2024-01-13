from django.urls import path
from . import views
from . import utils

app_name = 'customer_dashboard'

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('history_page/', views.history_page, name='history_page'),
    path('api/history/', views.history, name='history'),
    path('history/<str:openai_thread_id>/', views.thread_detail, name='thread_detail'),
    path('api/chat_with_gpt/', views.chat_with_gpt, name='chat_with_gpt'),
    path('api/order_history/', views.api_order_history, name='api_order_history'),
    path('api/user_goals/', views.track_goals, name='api_user_goals'),
    path('api/meal_plans/', views.meal_plans, name='api_meal_plans'),
    path('api/chat_logs/', views.chat_with_gpt, name='api_chat_logs'),
    path('api/update_week_shift/', views.update_week_shift, name='api_update_week_shift'),
    path('api/update_goal/', views.update_goal_api, name='api_update_goal'),
    path('api/food_preferences/', views.food_preferences, name='food_preferences'),
    path('api/update_food_preferences/', views.update_food_preferences, name='update_food_preferences'),
    # streamlit
    path('api/history_page/', views.api_history_page, name='api_history_page'),
    path('api/thread_history/', views.api_thread_history, name='api_thread_history'),
    path('api/thread_detail/<str:openai_thread_id>/', views.api_thread_detail_view, name='api_thread_detail'),
    path('api/goal_management/', views.api_goal_management, name='api_goal_management'),
    path('api/user_goal/', views.api_user_goal_view, name='api_user_goal_view'),
    path('api/adjust_week_shift/', utils.api_adjust_week_shift, name='api_adjust_week_shift'),
    path('api/adjust_current_week/', utils.api_adjust_current_week, name='api_adjust_current_week'),
    path('api/update_goal/', utils.api_update_goal, name='api_update_goal'),
    path('api/get_goal/', utils.api_get_goal, name='api_get_goal'),
    path('api/get_user_info/', utils.api_get_user_info, name='api_get_user_info'),
    path('api/access_past_orders/', utils.api_access_past_orders, name='api_access_past_orders'),
    path('api/api_ai_call/', views.api_ai_call, name='api_ai_call'),


]
