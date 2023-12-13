from django.urls import path
from . import views

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
    path('api/update_goal/', views.update_goal, name='api_update_goal'),
    path('api/food_preferences/', views.food_preferences, name='food_preferences'),
    path('api/update_food_preferences/', views.update_food_preferences, name='update_food_preferences'),
]
