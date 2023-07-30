from django.urls import path
from .views import ReviewCreateView, ReviewListView

app_name = 'reviews'

urlpatterns = [
    path('chef/<int:chef_id>/review/', ReviewCreateView.as_view(), name='chef_review_create'),
    path('menu/<int:menu_id>/review/', ReviewCreateView.as_view(), name='menu_review_create'),
    path('event/<int:event_id>/review/', ReviewCreateView.as_view(), name='event_review_create'),
    path('chef/<int:chef_id>/reviews/', ReviewListView.as_view(), name='chef_review_list'),
    path('menu/<int:menu_id>/reviews/', ReviewListView.as_view(), name='menu_review_list'),
    path('event/<int:event_id>/reviews/', ReviewListView.as_view(), name='event_review_list'),
]