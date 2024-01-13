from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

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
    path('api/register/', views.register_api_view, name='register_api'),   
    path('api/register/verify-email/', views.activate_account_api_view, name='verify_email_api'), 
    path('api/login/', views.login_api_view, name='login_api'),
    path('api/logout/', views.logout_api_view, name='logout_api'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/user_details/', views.user_details_view, name='user_details'),
    path('api/update_profile/', views.update_profile_api, name='update_profile_api'),
]
