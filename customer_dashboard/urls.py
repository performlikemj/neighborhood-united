from django.urls import path
from . import views
from . import utils

app_name = 'customer_dashboard'

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('history_page/', views.history_page, name='history_page'),
    path('api/history/', views.history, name='history'),
    path('history/<str:openai_thread_id>/', views.thread_detail, name='thread_detail'),
    path('api/order_history/', views.api_order_history, name='api_order_history'),
    path('api/user_goals/', views.track_goals, name='api_user_goals'),
    path('api/meal_plans/', views.meal_plans, name='api_meal_plans'),
    path('api/chat_logs/', views.chat_with_gpt, name='api_chat_logs'),
    path('api/update_week_shift/', views.update_week_shift, name='api_update_week_shift'),
    path('api/update_goal/', views.update_goal_api, name='api_update_goal'),
    # streamlit
    path('api/chat_with_gpt/', views.chat_with_gpt, name='chat_with_gpt'),
    path('api/guest_chat_with_gpt/', views.guest_chat_with_gpt, name='guest_chat_with_gpt'),
    path('api/get_message_status/<int:message_id>/', views.get_message_status, name='get_message_status'),
    path('api/ai_tool_call/', views.ai_tool_call, name='ai_tool_call'),
    path('api/guest_ai_tool_call/', views.guest_ai_tool_call, name='guest_ai_tool_call'),
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
    path('api/health_metrics/', views.api_user_metrics, name='api_get_health_metrics'),
    path('api/get_calories/', views.api_get_calories, name='api_get_calories'),
    path('api/add_calories/', views.api_add_calorie_intake, name='api_add_calories'),
    path('api/delete_calorie_intake/<int:record_id>/', views.api_delete_calorie_intake, name='api_delete_calorie_intake'),
    path('api/calorie_intake/<int:record_id>/', views.api_update_calorie_intake, name='api_update_calorie_intake'),
    path('api/user_summary/', views.api_user_summary, name='api_user_summary'),
]
