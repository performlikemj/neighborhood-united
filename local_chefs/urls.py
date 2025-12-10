from django.urls import path
from . import views

app_name = 'local_chefs'

urlpatterns = [
    # Legacy endpoints
    path('api/chef_service_areas/', views.chef_service_areas, name='chef_service_areas'),
    path('api/service_area_chefs/', views.service_area_chefs, name='service_area_chefs'),
    
    # Administrative area search and browsing
    path('api/areas/search/', views.search_areas, name='search_areas'),
    path('api/areas/<int:area_id>/', views.get_area, name='get_area'),
    path('api/areas/<int:area_id>/postal_codes/', views.get_area_postal_codes, name='get_area_postal_codes'),
    path('api/areas/<int:area_id>/children/', views.get_area_children, name='get_area_children'),
    path('api/areas/country/<str:country_code>/', views.get_areas_by_country, name='get_areas_by_country'),
    
    # Chef service area management (direct - for initial setup)
    path('api/chef/service-areas/', views.get_chef_service_areas, name='get_chef_service_areas'),
    path('api/chef/service-areas/add/', views.add_service_area, name='add_service_area'),
    path('api/chef/service-areas/<int:area_id>/remove/', views.remove_service_area, name='remove_service_area'),
    path('api/chef/service-areas/postal-codes/add/', views.add_postal_codes, name='add_postal_codes'),
    path('api/chef/service-areas/postal-codes/remove/', views.remove_postal_codes, name='remove_postal_codes'),
    
    # Service area requests (admin-approved changes)
    path('api/chef/area-status/', views.get_chef_area_status, name='get_chef_area_status'),
    path('api/chef/area-requests/', views.submit_area_request, name='submit_area_request'),
    path('api/chef/area-requests/<int:request_id>/', views.get_area_request, name='get_area_request'),
    path('api/chef/area-requests/<int:request_id>/cancel/', views.cancel_area_request, name='cancel_area_request'),
]