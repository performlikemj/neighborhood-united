from django.urls import path
from . import views

app_name = 'chef_admin'

urlpatterns = [
    path('dashboard/', views.chef_dashboard, name='chef_dashboard'),
    path('orders/', views.order_dashboard, name='order_dashboard'),
    # path('api/most_popular_dishes/', views.most_popular_dishes, name='most_popular_dishes'),
    path('api/sales_over_time/', views.sales_over_time, name='sales_over_time'),
    path('api/active_orders/', views.active_orders, name='active_orders'),
    path('api/all_orders/', views.all_orders, name='all_orders'),
    path('api/incomplete_orders/', views.incomplete_orders, name='incomplete_orders'),
    path('api/update_order_status/<int:order_id>/', views.update_order_status, name='update_order_status'),
]