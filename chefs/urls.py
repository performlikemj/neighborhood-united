from django.urls import path 
from . import views


app_name = 'chefs'

urlpatterns = [
    path('', views.chef_list, name='chef_list'),
    path('<int:chef_id>/', views.chef_detail, name='chef_detail'),
    path('chef_request/', views.chef_request, name='chef_request'),
    path('my-dishes/', views.chef_view, name='chef_view'),
    # New chef-related endpoints
    path('api/chefs/check-chef-status/', views.check_chef_status, name='check_chef_status'),
    path('api/chefs/submit-chef-request/', views.submit_chef_request, name='submit_chef_request'),
]

