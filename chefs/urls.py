from django.urls import path 
from . import views


app_name = 'chefs'

urlpatterns = [
    # Public API
    path('api/chefs/<int:chef_id>/', views.chef_public, name='chef_public'),
    path('api/public/<int:chef_id>/', views.chef_public, name='chef_public_id'),
    path('api/public/by-username/<str:username>/', views.chef_public_by_username, name='chef_public_by_username'),
    path('api/lookup/by-username/<str:username>/', views.chef_lookup_by_username, name='chef_lookup_by_username'),
    path('api/public/', views.chef_public_directory, name='chef_public_directory'),
    path('api/public/<int:chef_id>/serves-my-area/', views.chef_serves_my_area, name='chef_serves_my_area'),
    # React API endpoints for chef profile management
    path('api/me/chef/profile/', views.me_chef_profile, name='me_chef_profile'),
    path('api/me/chef/profile/update/', views.me_update_profile, name='me_update_profile'),
    path('api/me/chef/photos/', views.me_upload_photo, name='me_upload_photo'),
    path('api/me/chef/photos/<int:photo_id>/', views.me_delete_photo, name='me_delete_photo'),
    # New chef-related endpoints
    path('api/chefs/check-chef-status/', views.check_chef_status, name='check_chef_status'),
    path('api/chefs/submit-chef-request/', views.submit_chef_request, name='submit_chef_request'),
]

