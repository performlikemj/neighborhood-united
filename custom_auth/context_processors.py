def role_context_processor(request):
    # Check if the user is authenticated before accessing `current_role`
    if request.user.is_authenticated:
        current_role = request.user.current_role
    else:
        current_role = None

    return {'current_role': current_role}
