"""Custom throttles for authenticated user traffic."""

from rest_framework.throttling import SimpleRateThrottle


class AuthenticatedBurstThrottle(SimpleRateThrottle):
    """Short-term burst control for authenticated users.

    Only applies to authenticated requests and is ignored for safe (read-only)
    HTTP methods so profile fetches do not hit the throttle bucket.
    """

    scope = "auth_burst"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None

        if request.method in ("GET", "HEAD", "OPTIONS"):  # skip read-only
            return None

        return self.cache_format % {"scope": self.scope, "ident": user.id}


class AuthenticatedDailyThrottle(SimpleRateThrottle):
    """Daily budget control for authenticated users."""

    scope = "auth_daily"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None

        return self.cache_format % {"scope": self.scope, "ident": user.id}
