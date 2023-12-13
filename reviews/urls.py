from django.urls import path
from .views import ReviewCreateView, ReviewListView, ReviewUpdateView, ReviewDeleteView

app_name = 'reviews'

urlpatterns = [
    path('chef/<int:chef_id>/review/', ReviewCreateView.as_view(), name='chef_review_create'),
    path('meal/<int:meal_id>/review/', ReviewCreateView.as_view(), name='meal_review_create'),
    path('event/<int:event_id>/review/', ReviewCreateView.as_view(), name='event_review_create'),
    path('chef/<int:chef_id>/reviews/', ReviewListView.as_view(), name='chef_review_list'),
    path('meal/<int:meal_id>/reviews/', ReviewListView.as_view(), name='meal_review_list'),
    path('event/<int:event_id>/reviews/', ReviewListView.as_view(), name='event_review_list'),
    path('my_reviews/', ReviewListView.as_view(), name='my_review_list'),  # Added this line
    path('edit_review/<int:pk>/', ReviewUpdateView.as_view(), name='edit_review'),
    path('delete_review/<int:pk>/', ReviewDeleteView.as_view(), name='delete_review'),
]    
