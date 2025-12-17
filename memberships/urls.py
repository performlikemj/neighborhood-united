from django.urls import path

from . import views

app_name = 'memberships'

urlpatterns = [
    # Subscription management
    path('subscribe/', views.create_checkout_session, name='subscribe'),
    path('status/', views.membership_status, name='status'),
    path('portal/', views.create_portal_session, name='portal'),
    path('cancel/', views.cancel_membership, name='cancel'),
    path('payments/', views.payment_history, name='payments'),
]




