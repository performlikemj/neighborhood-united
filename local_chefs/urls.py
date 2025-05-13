from django.urls import path
from . import views

app_name = 'local_chefs'

urlpatterns = [
    path('api/chef_service_areas/', views.chef_service_areas, name='chef_service_areas'),
    path('api/service_area_chefs/', views.service_area_chefs, name='service_area_chefs'),
]