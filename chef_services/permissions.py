from rest_framework.permissions import BasePermission


class IsChefOwnerOfOffering(BasePermission):
    """Allows access only to the owning chef of the offering/tier."""
    def has_object_permission(self, request, view, obj):
        # obj can be offering or tier (which has offering)
        offering = getattr(obj, 'offering', obj)
        chef = getattr(offering, 'chef', None)
        return bool(chef and chef.user_id == getattr(request.user, 'id', None))


class IsOrderOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return getattr(obj, 'customer_id', None) == getattr(request.user, 'id', None)

