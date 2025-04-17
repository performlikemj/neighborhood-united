from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
import logging
import json
from customer_dashboard.models import AssistantEmailToken
from customer_dashboard.views import assistant

logger = logging.getLogger(__name__)

# secure_email_integration.py
@csrf_exempt
@require_http_methods(["POST"]) 
def process_email(request):
    """API endpoint for processing emails from n8n"""
    try:
        # Parse the request body
        data = json.loads(request.body)
        sender_email = data.get('sender_email')
        token = data.get('token')  # Extracted from assistant+{token}@domain.com
        message_content = data.get('message_content')
        conversation_token = data.get('conversation_token')
        
        # Validate required parameters
        if not sender_email or not token or not message_content:
            logger.error(f"Missing required parameters: {data}")
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
        
        # Validate and get user from token
        is_valid, user, token_obj = AssistantEmailToken.validate_and_update_token(token)
        
        if not is_valid or not user:
            logger.error(f"Invalid token: {token}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid token'
            }, status=403)
        
        # Verify sender email matches token owner
        if user.email != sender_email:
            logger.warning(f"Email mismatch: token user {user.email}, sender {sender_email}")
            return JsonResponse({
                'status': 'error',
                'message': 'Sender email does not match token owner'
            }, status=403)
        
        # Process the message with the assistant
        user_id = str(user.id)
        result = assistant.send_message(user_id, message_content)
        
        # Add the token to the result for n8n to use in the reply address
        result['token'] = token
        
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to process email: {str(e)}'
        }, status=500)
