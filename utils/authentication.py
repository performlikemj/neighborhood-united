from rest_framework.authentication import BaseAuthentication
from django.contrib.auth.models import AnonymousUser

class GuestIDAuthentication(BaseAuthentication):
    """
    Extract guest_id from request data and save to session.
    This runs before quotas are checked but after request parsing.
    """
    def authenticate(self, request):
        # Don't access request.user here as it causes circular dependency
        # Instead, check if the request already has an authenticated _user attribute
        if hasattr(request, '_user') and request._user and request._user.is_authenticated:
            return None
        
        # If we already have a guest_id in session, prioritize that over anything else
        if getattr(request, '_user', None) not in (None, AnonymousUser()):
            return None                 # someone else has authenticated
        if 'guest_id' in request.session:
            return None        # already set
            
        # Get guest_id from request data if available
        guest_id = None
        if hasattr(request, 'data') and isinstance(request.data, dict):
            guest_id = request.data.get('guest_id')
            
        # If found, save to session for middleware/quota access
        if guest_id:
            request.session['guest_id'] = guest_id
            request.session.modified = True
            print(f"AUTH: Saved guest_id {guest_id} to session")
            
        # Return None to let Django continue the auth chain
        return None 