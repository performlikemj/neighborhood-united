from django.urls import path
from . import views

app_name = 'custom_auth'

urlpatterns = [
    path('', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-email/', views.EmailChangeView.as_view(), name='change_email'),
    path('switch-roles/', views.switch_roles, name='switch_roles'),  
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('activate/<uidb64>/<token>/', views.activate_view, name='activate'),
    path('verify-email/', views.verify_email_view, name='verify_email'),
    path('confirm-email/<str:uidb64>/<str:token>', views.confirm_email, name='confirm_email'),
    path('user/re-request-email-change/', views.re_request_email_change, name='re_request_email_change'),  
]
