from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    # API endpoints
    path('api/profile/', views.user_gamification_profile, name='api_profile'),
    path('api/leaderboard/', views.leaderboard, name='api_leaderboard'),
    path('api/achievements/', views.achievements_list, name='api_achievements'),
    path('api/points-history/', views.points_history, name='api_points_history'),
    path('api/streamlit-data/', views.streamlit_data, name='api_streamlit_data'),
] 