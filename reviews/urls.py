from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('chef/<int:chef_id>/review/', views.ReviewCreateView.as_view(), name='chef_review_create'),
    path('meal/<int:meal_id>/review/', views.ReviewCreateView.as_view(), name='meal_review_create'),
    path('event/<int:event_id>/review/', views.ReviewCreateView.as_view(), name='event_review_create'),
    path('chef/<int:chef_id>/reviews/', views.ReviewListView.as_view(), name='chef_review_list'),
    path('meal/<int:meal_id>/reviews/', views.ReviewListView.as_view(), name='meal_review_list'),
    path('event/<int:event_id>/reviews/', views.ReviewListView.as_view(), name='event_review_list'),
    path('my_reviews/', views.ReviewListView.as_view(), name='my_review_list'),  # Added this line
    path('edit_review/<int:pk>/', views.ReviewUpdateView.as_view(), name='edit_review'),
    path('delete_review/<int:pk>/', views.ReviewDeleteView.as_view(), name='delete_review'),
    path('api/meal/<int:meal_id>/review/', views.create_meal_review, name='meal_review_create_api'),
    path('api/meal/<int:meal_id>/reviews/', views.list_meal_reviews, name='list_meal_reviews'),
    path('api/meal_plan/<int:meal_plan_id>/review/', views.create_meal_plan_review, name='meal_plan_review_create'),
    path('api/meal_plan/<int:meal_plan_id>/reviews/', views.list_meal_plan_reviews, name='meal_plan_review_list'),
]    
