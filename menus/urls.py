from django.urls import path
from . import views

app_name = 'menus'

urlpatterns = [
    path('', views.dish_list, name='dish_list'),
    path('dish/<int:dish_id>/', views.dish_detail, name='dish_detail'),
    path('add_to_cart/<int:menu_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('create_dish/', views.create_dish, name='create_dish'),
    path('update_dish/<int:dish_id>/', views.update_dish, name='update_dish'),
    path('create_ingredient/', views.create_ingredient, name='create_ingredient'),
    path('create_menu/', views.create_menu, name='create_menu'),
    path('menu_detail/<int:menu_id>/', views.menu_detail, name='menu_detail'),
    path('menu_list/', views.menu_list, name='menu_list'),
    path('menus_with_dish/<int:dish_id>/', views.menus_with_dish, name='menus_with_dish'),
    path('chef/<int:chef_id>/weekly_menu/', views.chef_weekly_menu, name='chef_weekly_menu'),
    path('api/search_ingredients/', views.api_search_ingredients, name='api_search_ingredients'),
    path('api/create_ingredient/', views.api_create_ingredient, name='api_create_ingredient'),
]
