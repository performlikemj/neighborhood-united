"""
Model selection utilities for OpenAI API calls.
"""
from django.conf import settings
from utils.openai_helpers import token_length
from utils.quotas import hit_quota

# Available models in order of capability/cost
MODEL_GPT41 = "gpt-4.1"
MODEL_GPT41_MINI = "gpt-4.1-mini"
MODEL_GPT41_NANO = "gpt-4.1-nano"

# Smart keywords that trigger upgrade to GPT-4.1
SMART_KEYWORDS = {
    # meal planning
    "meal plan", "weekly menu", "macro breakdown", "calorie split",
    "bulk prep", "shopping list", "modify meal", "replace meal",
    # chef / order flow
    "local chef", "chef meal", "place order", "order details",
    "update order", "cancel order", "refund",
    # pantry
    "check pantry", "pantry items", "expiring items", "replenish", "supermarket",
    # goals / summaries
    "update goal", "get goal", "health summary", "progress report",
    # emergency supplies
    "emergency supply", "disaster kit",
    # payment
    "pay", "payment", "payment link", "checkout", "stripe", "generate link",
}

# Complexity threshold for determining when to use the advanced model
COMPLEXITY_THRESHOLD = 80  # Tokens

def choose_model(user_id, is_guest: bool, question: str, history_tokens: int = 0) -> str:
    """
    Choose the appropriate model based on:
    1. Keyword matching (upgrade to GPT-4.1 if any smart keyword is present)
    2. Total token complexity (question + history)
    3. User authentication status
    4. User's quota usage
    
    Returns the model string to use for the API call.
    """
    # Convert user_id to string for consistent handling
    user_id = str(user_id)
    
    # Measure question complexity by token count
    tl = token_length(question)
    total = tl + history_tokens
    print(f"MODEL_SELECTION: User {user_id} (guest={is_guest}) - Question length: {tl} tokens, Total with history: {total} tokens")
    
    # Check for keyword matches
    question_lower = question.lower()
    matching_keywords = [kw for kw in SMART_KEYWORDS if kw in question_lower]
    
    # Determine if we should upgrade based on keywords or complexity
    upgrade = matching_keywords or total >= COMPLEXITY_THRESHOLD
    
    if matching_keywords:
        print(f"MODEL_SELECTION: Upgrading due to keywords: {matching_keywords}")
    elif total >= COMPLEXITY_THRESHOLD:
        print(f"MODEL_SELECTION: Upgrading due to token complexity: {total} >= {COMPLEXITY_THRESHOLD}")
    
    # 1) Decide "ideal" model based on upgrade criteria
    ideal = MODEL_GPT41 if upgrade else MODEL_GPT41_MINI
    
    # 2) Apply per-user quotas
    if is_guest:
        if ideal == MODEL_GPT41_MINI:
            quota_exhausted = hit_quota(user_id, "mini_daily", settings.GPT41_MINI_GUEST_LIMIT)
            if quota_exhausted:
                print(f"MODEL_SELECTION: Guest {user_id} quota exhausted - Using {MODEL_GPT41_NANO}")
                return MODEL_GPT41_NANO
        else:
            # Guests never get full GPT-4.1, downgrade to mini
            print(f"MODEL_SELECTION: Guest {user_id} - Using {MODEL_GPT41_MINI} (downgraded from {MODEL_GPT41})")
            return MODEL_GPT41_MINI
    else:
        if ideal == MODEL_GPT41:
            quota_exhausted = hit_quota(user_id, "gpt41_daily", settings.GPT41_AUTH_LIMIT)
            if quota_exhausted:
                print(f"MODEL_SELECTION: User {user_id} quota exhausted - Using {MODEL_GPT41_MINI}")
                return MODEL_GPT41_MINI
    
    print(f"MODEL_SELECTION: Selected {ideal} for user {user_id}")
    return ideal 