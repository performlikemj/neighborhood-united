from rest_framework import permissions
from custom_auth.models import UserRole

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            user_role = UserRole.objects.get(user=request.user)
            return user_role.current_role == 'customer'
        except UserRole.DoesNotExist:
            return False
