from django.urls import path
from . import views
from . import utils
from . import secure_email_integration
from .api import my_chefs as my_chefs_api

app_name = 'customer_dashboard'

urlpatterns = [
    # Client Portal - My Chefs endpoints (multi-chef support)
    path('api/my-chefs/', my_chefs_api.get_my_chefs, name='get_my_chefs'),
    path('api/my-chefs/<int:chef_id>/', my_chefs_api.get_chef_hub, name='get_chef_hub'),
    path('api/my-chefs/<int:chef_id>/orders/', my_chefs_api.get_chef_orders, name='get_chef_orders'),

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
    path('api/debug_threads/', views.debug_threads, name='debug_threads'),
    path('api/adjust_week_shift/', utils.api_adjust_week_shift, name='api_adjust_week_shift'),
    path('api/adjust_current_week/', utils.api_adjust_current_week, name='api_adjust_current_week'),
    path('api/update_goal/', utils.api_update_goal, name='api_update_goal'),
    path('api/get_goal/', utils.api_get_goal, name='api_get_goal'),
    path('api/get_user_info/', utils.api_get_user_info, name='api_get_user_info'),
    path('api/access_past_orders/', utils.api_access_past_orders, name='api_access_past_orders'),

    path('api/user_summary/', views.api_user_summary, name='api_user_summary'),
    path('api/user_summary_status/', views.api_user_summary_status, name='api_user_summary_status'),
    path('api/stream_user_summary/', views.api_stream_user_summary, name='api_stream_user_summary'),
    path('api/recommend_follow_up/', views.api_recommend_follow_up, name='api_recommend_follow_up'),

    # Updated Endpoints for the new AI Assistant
    path('api/assistant/send-message/', views.send_message, name='send_message'),
    path('api/assistant/stream-message/', views.stream_message, name='stream_message'),
    path('api/assistant/guest-stream-message/', views.guest_stream_message, name='guest_stream_message'),
    path('api/assistant/reset-conversation/', views.reset_conversation, name='reset_conversation'),
    path('api/assistant/conversation/<str:user_id>/history/', views.get_conversation_history, name='get_conversation_history'),
    path('api/assistant/new-conversation/', views.new_conversation, name='new_conversation'),
    path('api/assistant/guest-new-conversation/', views.guest_new_conversation, name='guest_new_conversation'),
    path('api/assistant/onboarding/stream-message/', views.onboarding_stream_message, name='onboarding_stream_message'),
    path('api/assistant/onboarding/new-conversation/', views.onboarding_new_conversation, name='onboarding_new_conversation'),
    path('api/email-assistant/process/', secure_email_integration.process_email, name='process_email'),
    # DEBUG-only preview routes
    path('debug/assistant-email/preview/', views.preview_assistant_email, name='preview_assistant_email'),
    path('debug/assistant-email/', views.preview_index, name='assistant_email_preview_index'),

]
