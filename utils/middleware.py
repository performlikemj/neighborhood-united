"""
Custom middleware for request processing.
"""
from django.utils.deprecation import MiddlewareMixin
from utils.model_selection import choose_model, MODEL_GPT41_MINI, MODEL_GPT41_NANO
from utils.openai_helpers import token_length
from utils.redis_client import get, set, delete
import logging

logger = logging.getLogger(__name__)

class ModelSelectionMiddleware(MiddlewareMixin):
    """
    Middleware that selects the appropriate OpenAI model based on:
    - User authentication status
    - Request complexity
    - User quotas
    - Conversation history complexity
    
    This allows API views to access the selected model through request.openai_model
    """
    
    def process_request(self, request):
        """
        Process the request to determine the appropriate model.
        """
        # Default to a simpler model if we can't determine the complexity
        default_model = MODEL_GPT41_MINI
        
        # Extract the user (if authenticated)
        user_id = None
        is_guest = True
        guest_id = None  # Initialize guest_id to None
        
        if request.user and request.user.is_authenticated:
            user_id = request.user.id
            is_guest = False
        else:
            # Make sure session key exists for guests
            if not request.session.session_key:
                request.session.create()  # Force creation of a session key
            
            session_key = request.session.session_key
            
            # Check request.data for guest_id (for POST/PUT JSON requests)
            if hasattr(request, 'data') and isinstance(request.data, dict) and 'guest_id' in request.data:
                guest_id = request.data.get('guest_id')
                logger.info(f"MIDDLEWARE: Found guest_id {guest_id} in request.data")
            
            # Fallback to session if not in data
            if not guest_id:
                guest_id = request.session.get('guest_id')
                
            # If we're still missing guest_id, fall back to cookie-backed session_key
            if not guest_id:
                guest_id = session_key
            
            # Diagnostic logging
            logger.info(f"MIDDLEWARE: Session key: {session_key}, Guest ID: {guest_id}")
            
            # Use the guest_id from session if available, otherwise use session_key
            user_id = guest_id
        
        # Get request content (for complexity measurement)
        # Try common places where content might be found
        content = ''
        
        if request.method == 'POST':
            # For JSON API requests
            if hasattr(request, 'data') and request.data:
                if isinstance(request.data, dict) and 'message' in request.data:
                    content = request.data.get('message', '')
                elif isinstance(request.data, dict) and 'question' in request.data:
                    content = request.data.get('question', '')
            
            # For form submissions
            elif request.POST:
                content = request.POST.get('message', request.POST.get('question', ''))
        
        # Calculate conversation history tokens (last 10 turns from cache)
        history_tokens = 0
        if user_id:
            # Get conversation history from cache (keyed by user_id)
            conversation_key = f"conversation_history:{user_id}"
            history = get(conversation_key, [])
            
            # Calculate tokens from history (up to last 10 turns)
            history_slice = history[-10:] if len(history) > 10 else history
            history_tokens = sum(token_length(msg) for msg in history_slice)
            
            # Add current message to history for next time
            if content:
                if len(history) >= 50:  # Limit history to last 50 messages
                    history = history[-49:] 
                history.append(content)
                set(conversation_key, history, 86400)  # Store for 24 hours
        
        # Select the model
        if user_id and content:
            model = choose_model(user_id, is_guest, content, history_tokens)
        else:
            # If we can't determine content complexity, use a reasonable default
            model = MODEL_GPT41_NANO if is_guest else default_model
        
        # Attach to the request object for views to access
        request.openai_model = model 