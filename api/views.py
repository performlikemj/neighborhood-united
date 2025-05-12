from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    """
    Custom exception handler for API responses.
    
    Provides more helpful messaging for throttled requests.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If it's a throttling exception, customize the response
    if isinstance(exc, Throttled):
        custom_response_data = {
            'error': 'rate_limit_exceeded',
            'message': 'You have reached your daily limit for this model.',
            'detail': 'Please try again tomorrow or use a different model.',
        }
        
        # Add wait time if available
        if exc.wait:
            custom_response_data['wait'] = exc.wait
            
        return Response(custom_response_data, status=429)
    
    return response 