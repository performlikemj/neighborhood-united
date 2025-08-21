"""
Custom throttling classes for API rate limiting.
"""
from rest_framework.throttling import SimpleRateThrottle

class GPT4DailyThrottle(SimpleRateThrottle):
    """
    Throttle for limiting access to GPT-4.1 models.
    
    This throttle limits authenticated users to a fixed number of
    requests per day to endpoints that use the GPT-4.1 model.
    """
    scope = "gpt4"

    def get_cache_key(self, request, view):
        # Only throttle authenticated users
        if not request.user or not request.user.is_authenticated:
            return None  # Let guest throttles handle unauthenticated users
        
        # Only apply to model endpoints
        if not self._should_throttle(request):
            return None
            
        # Use the user ID as the cache key
        return f"{self.scope}:{request.user.id}"
        
    def _should_throttle(self, request):
        """Only throttle requests to assistant message endpoints"""
        # Identify model-related endpoints
        model_endpoints = [
            '/meals/assistant/stream-message/',
            '/meals/assistant/message/',
            '/customer_dashboard/api/assistant/stream-message/',
            '/customer_dashboard/api/assistant/message/'
        ]
        
        # Check if the current path matches any model endpoint
        for endpoint in model_endpoints:
            if endpoint in request.path:
                return True
                
        # Don't throttle other endpoints
        return False

class GuestGPT4MiniThrottle(SimpleRateThrottle):
    """
    Throttle for limiting guest access to GPT-4.1-mini models.
    
    This throttle limits guest users to a fixed number of
    requests per day to endpoints that use the GPT-4.1-mini model.
    """
    scope = "gpt4_mini_guest"

    def get_cache_key(self, request, view):
        # Only throttle unauthenticated users
        if request.user and request.user.is_authenticated:
            return None  # Let authenticated throttles handle it
        
        # Only apply to model endpoints
        if not self._should_throttle(request):
            return None
        
        # Ensure session exists for guests
        if not request.session.session_key:
            request.session.create()
            
        # Use the session key or IP as the cache key
        if request.session.session_key:
            return f"{self.scope}:{request.session.session_key}"
        else:
            # Fall back to IP address if no session key
            return f"{self.scope}:{self.get_ident(request)}"
    
    def _should_throttle(self, request):
        """Only throttle requests to assistant message endpoints"""
        # Identify model-related endpoints
        model_endpoints = [
            '/meals/assistant/stream-message/',
            '/meals/assistant/message/',
            '/customer_dashboard/api/assistant/stream-message/',
            '/customer_dashboard/api/assistant/message/'
        ]
        
        # Check if the current path matches any model endpoint
        for endpoint in model_endpoints:
            if endpoint in request.path:
                return True
                
        # Don't throttle other endpoints
        return False 