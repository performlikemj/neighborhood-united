from functools import wraps

from django.conf import settings
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import urlencode

from .models import UserRole

_VALID_ROLES = {"chef", "customer"}


def require_role(required_role):
    """Ensure the authenticated user is in the requested role, otherwise prompt."""
    if required_role not in _VALID_ROLES:
        raise ValueError(f"Unsupported role: {required_role}")

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                login_url = resolve_url(settings.LOGIN_URL)
                query = urlencode({"next": request.get_full_path()})
                return redirect(f"{login_url}?{query}")

            user_role, _ = UserRole.objects.get_or_create(
                user=request.user,
                defaults={"current_role": "customer"},
            )

            if user_role.current_role == required_role:
                return view_func(request, *args, **kwargs)

            context = {
                "required_role": required_role,
                "current_role": user_role.current_role,
                "next_url": request.get_full_path(),
                "can_access_chef": user_role.is_chef,
            }
            return render(request, "custom_auth/role_prompt.html", context, status=403)

        return _wrapped

    return decorator
