"""
Utility functions for OpenAI API interactions.
"""
import tiktoken

# Initialize the encoder once
# Use cl100k_base encoding (used by gpt-4, gpt-4o, o1, o3 models)
enc = tiktoken.get_encoding("cl100k_base")

def token_length(text: str) -> int:
    """
    Return approximate OpenAI token count for a string.
    Uses the same tokenizer as OpenAI for accurate counts.
    """
    return len(enc.encode(text)) 