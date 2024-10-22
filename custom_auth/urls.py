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
    path('activate/<uidb64>/<token>/', views.activate_view, name='activate'),
    path('verify-email/', views.verify_email_view, name='verify_email'),
    path('confirm-email/<str:uidb64>/<str:token>', views.confirm_email, name='confirm_email'),
    path('user/re-request-email-change/', views.re_request_email_change, name='re_request_email_change'),
    path('api/countries/', views.get_countries, name='get_countries'),
    path('api/register/', views.register_api_view, name='register_api'),   
    path('api/register/verify-email/', views.activate_account_api_view, name='verify_email_api'), 
    path('api/login/', views.login_api_view, name='login_api'),
    path('api/logout/', views.logout_api_view, name='logout_api'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/user_details/', views.user_details_view, name='user_details'),
    path('api/address_details/', views.address_details_view, name='address_details'),
    path('api/update_profile/', views.update_profile_api, name='update_profile_api'),
    path('api/password_reset_request/', views.password_reset_request, name='password_reset_request'),
    path('api/change_password/', views.change_password, name='change_password'),
    path('api/reset_password/', views.reset_password, name='reset_password'),
    path('api/switch_role/', views.switch_role_api, name='switch_roles_api'),
    path('api/resend-activation-link/', views.resend_activation_link, name='resend_activation_link'),
    path('api/delete_account/', views.delete_account, name='delete_account'),
]
