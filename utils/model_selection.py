"""
Model selection utilities for Groq API calls.
"""
from django.conf import settings
from utils.openai_helpers import token_length
from utils.quotas import hit_quota
import os

import logging

logger = logging.getLogger(__name__)

# Get the default Groq model from settings
def _get_groq_model():
    return getattr(settings, 'GROQ_MODEL', None) or os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')

# Complexity threshold for determining when to use the advanced model
COMPLEXITY_THRESHOLD = 80  # Tokens

def choose_model(user_id, is_guest: bool, question: str, history_tokens: int = 0) -> str:
    """
    Choose the appropriate Groq model.
    
    Currently returns the configured GROQ_MODEL for all requests.
    The quota system can be used to limit usage if needed.
    
    Returns the model string to use for the Groq API call.
    """
    # Convert user_id to string for consistent handling
    user_id = str(user_id)
    
    # Measure question complexity by token count
    tl = token_length(question)
    total = tl + history_tokens
    
    # Get the configured Groq model
    model = _get_groq_model()
    
    logger.info(f"MODEL_SELECTION: Using Groq model {model} for user {user_id} (tokens: {total})")
    return model 
