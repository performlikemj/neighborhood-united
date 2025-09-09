"""
Utility functions for OpenAI API interactions.
"""
import tiktoken

# Initialize the encoder once
# Use a well-known model name that tiktoken recognizes
# gpt-4 tokenizer works for gpt-5 family as well
enc = tiktoken.encoding_for_model("gpt-5")

def token_length(text: str) -> int:
    """
    Return approximate OpenAI token count for a string.
    Uses the same tokenizer as OpenAI for accurate counts.
    """
    return len(enc.encode(text)) 