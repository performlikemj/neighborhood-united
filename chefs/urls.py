from django.urls import path 
from .views import chef_list, chef_detail, chef_request, chef_view


app_name = 'chefs'

urlpatterns = [
    path('', chef_list, name='chef_list'),
    path('<int:chef_id>/', chef_detail, name='chef_detail'),
    path('chef_request/', chef_request, name='chef_request'),
    path('my-dishes/', chef_view, name='chef_view'),

]

