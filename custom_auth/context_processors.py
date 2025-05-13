from .models import UserRole

def role_context_processor(request):
    # Check if the user is authenticated before accessing `current_role`
    if request.user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=request.user)
            current_role = user_role.current_role
        except UserRole.DoesNotExist:
            current_role = None
    else:
        current_role = None

    return {'current_role': current_role}
