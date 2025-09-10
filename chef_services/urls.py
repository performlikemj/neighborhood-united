from django.urls import path
from . import views


urlpatterns = [
    # Offerings
    path('offerings/', views.offerings, name='service_offerings'),
    path('offerings/<int:offering_id>/', views.update_offering, name='service_offering_update'),
    path('offerings/<int:offering_id>/tiers/', views.add_tier, name='service_offering_add_tier'),
    path('tiers/<int:tier_id>/', views.update_tier, name='service_tier_update'),
    path('my/offerings/', views.my_offerings, name='service_my_offerings'),

    # Orders
    path('orders/', views.create_order, name='service_create_order'),
    path('orders/<int:order_id>/', views.get_order, name='service_get_order'),
    path('orders/<int:order_id>/checkout', views.checkout_order, name='service_checkout_order'),
    path('orders/<int:order_id>/cancel', views.cancel_order, name='service_cancel_order'),
]

