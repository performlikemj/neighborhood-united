from django.contrib.auth.decorators import user_passes_test

def chef_required(function=None, login_url='chefs:chef_list'):
    decorator = user_passes_test(
        lambda u: u.is_authenticated and u.current_role == 'chef',
        login_url=login_url,
    )
    if function:
        return decorator(function)
    return decorator

def customer_required(function=None, login_url='chefs:chef_list'):
    decorator = user_passes_test(
        lambda u: u.is_authenticated and u.current_role == 'customer',
        login_url=login_url,
    )
    if function:
        return decorator(function)
    return decorator
