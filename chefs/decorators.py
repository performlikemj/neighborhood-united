from django.contrib.auth.decorators import user_passes_test
from custom_auth.models import UserRole

def _is_role(user, role_name):
    if not user.is_authenticated:
        return False
    try:
        user_role = UserRole.objects.get(user=user)
        return user_role.current_role == role_name
    except UserRole.DoesNotExist:
        return False

def chef_required(function=None, login_url='chefs:chef_list'):
    decorator = user_passes_test(
        lambda u: _is_role(u, 'chef'),
        login_url=login_url,
    )
    if function:
        return decorator(function)
    return decorator

def customer_required(function=None, login_url='chefs:chef_list'):
    decorator = user_passes_test(
        lambda u: _is_role(u, 'customer'),
        login_url=login_url,
    )
    if function:
        return decorator(function)
    return decorator
