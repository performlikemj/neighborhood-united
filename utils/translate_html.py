import re
import uuid
import os
import redis
from bs4 import BeautifulSoup
import logging
from django.conf.locale import LANG_INFO
import requests
import traceback
from openai import OpenAI
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_KEY"))

VAR_RX = re.compile(r"({{.*?}}|{%.*?%})", re.S)

# Initialize Redis connection with proper SSL handling
def get_redis_client():
    """Get Redis client with proper SSL configuration for Azure Redis."""
    redis_url = os.getenv('REDIS_URL', '') or os.getenv('CELERY_BROKER_URL', '')
    
    if not redis_url:
        logger.warning("No Redis URL found in environment variables")
        return None
    
    try:
        # Try direct connection - URL now contains lowercase ssl_cert_reqs=none
        # that both Celery and redis-py accept
        client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=10,
            socket_timeout=10,
            retry_on_timeout=True,
            decode_responses=True
        )
        
        # Test the connection
        client.ping()
        logger.info("Redis connection successful")
        return client
        
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        
        # Fallback: try basic connection without SSL options
        try:
            client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=True
            )
            client.ping()
            logger.warning("Redis connected with basic configuration (fallback)")
            return client
            
        except Exception as fallback_error:
            logger.error(f"Redis fallback connection failed: {fallback_error}")
            return None

# Global Redis connection instance
_redis_connection = None

def _reset_redis_connection():
    """Reset the global Redis connection."""
    global _redis_connection
    _redis_connection = None

def _get_or_create_redis_connection():
    """Get or create Redis connection with automatic retry on failure."""
    global _redis_connection
    
    if _redis_connection is None:
        _redis_connection = get_redis_client()
    
    # Test the connection and reset if it's not working
    if _redis_connection is not None:
        try:
            _redis_connection.ping()
        except Exception as e:
            logger.warning(f"Redis connection test failed, resetting: {e}")
            _redis_connection = get_redis_client()
    
    return _redis_connection

def get_cached_translation(cache_key):
    """Get cached translation from Redis."""
    try:
        connection = _get_or_create_redis_connection()
        
        if connection is None:
            logger.warning("Redis connection not available for caching")
            return None
            
        return connection.get(cache_key)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as conn_error:
        logger.warning(f"Redis connection error while retrieving cache, resetting connection: {conn_error}")
        _reset_redis_connection()
        return None
    except Exception as e:
        logger.error(f"Error retrieving from Redis cache: {str(e)}")
        return None

def set_cached_translation(cache_key, value, timeout=3600):
    """Set cached translation in Redis."""
    try:
        connection = _get_or_create_redis_connection()
        
        if connection is None:
            logger.warning("Redis connection not available for caching")
            return False
            
        connection.setex(cache_key, timeout, value)
        return True
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as conn_error:
        logger.warning(f"Redis connection error while setting cache, resetting connection: {conn_error}")
        _reset_redis_connection()
        return False
    except Exception as e:
        logger.error(f"Error setting Redis cache: {str(e)}")
        return False

def _mask_vars(html: str):
    mapping = {}
    def repl(m):
        token = f"__VAR_{uuid.uuid4().hex}__"
        mapping[token] = m.group(0)
        return token
    return VAR_RX.sub(repl, html), mapping

def _unmask(html: str, mapping: dict):
    for tok, original in mapping.items():
        html = html.replace(tok, original)
    return html

def _get_language_name(language_code):
    """
    Returns the full language name for a given language code.
    Falls back to the code itself if the language is not found.
    """
    if language_code in LANG_INFO and 'name' in LANG_INFO[language_code]:
        return LANG_INFO[language_code]['name']
    return language_code

def translate_paragraphs(html: str, target_lang: str) -> str:
    """
    Translates HTML paragraphs to the target language while preserving
    Django template variables and HTML structure.
    
    Args:
        html (str): The HTML content to translate
        target_lang (str): Target language code (e.g., 'es', 'fr', 'ja')
        
    Returns:
        str: Translated HTML with structure preserved
    """
    if not target_lang or target_lang.lower() == "en":
        return html  # nothing to do if English or no language specified
    
    # Get the full language name for better translation accuracy
    target_lang_name = _get_language_name(target_lang)
    logger.info(f"Translating to {target_lang_name} (code: {target_lang})")
    
    # Check Redis cache first to avoid redundant API calls
    cache_key = f"translated_html:{hash(html)}:{target_lang}"
    cached_result = get_cached_translation(cache_key)
    if cached_result:
        logger.info(f"Retrieved translation from Redis cache")
        return cached_result

    try:
        masked_html, mapping = _mask_vars(html)
        soup = BeautifulSoup(masked_html, "html.parser")

        # Get all paragraphs with actual content
        paragraphs = [p for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li"]) if p.get_text(strip=True)]
        logger.info(f"Found {len(paragraphs)} paragraphs/elements to translate")
        
        if not paragraphs:
            logger.warning("No paragraphs found to translate")
            return html
        
        # Process paragraphs in batches to reduce API calls
        batch_size = 3  # Smaller batch size for more accurate translations
        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i+batch_size]
            
            # Prepare batch content with clear markers
            batch_contents = []
            for idx, p in enumerate(batch):
                # Preserve any nested tags by getting the full HTML content
                original_html = str(p)
                batch_contents.append(f"[BLOCK_{idx}]\n{original_html}\n[/BLOCK_{idx}]")
                
            if not batch_contents:
                continue
                
            batch_text = "\n\n".join(batch_contents)
            
            # Call OpenAI API with the batch
            try:
                response = client.responses.create(
                    model="gpt-4.1-nano", 
                    temperature=0.2,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                f"Translate the following HTML blocks to {target_lang_name}. "
                                "IMPORTANT: Preserve all HTML tags and attributes exactly as they are. "
                                "Do not modify any HTML structure, only translate the human-readable text content. "
                                "Keep all [BLOCK_X] and [/BLOCK_X] markers intact."
                            )
                        },
                        {"role": "user", "content": batch_text}
                    ]
                )
                
                translated_text = response.output_text
                
                # Process each block separately
                for idx, p in enumerate(batch):
                    block_start = f"[BLOCK_{idx}]\n"
                    block_end = f"\n[/BLOCK_{idx}]"
                    
                    # Extract the translated block
                    start_pos = translated_text.find(block_start)
                    end_pos = translated_text.find(block_end)
                    
                    if start_pos != -1 and end_pos != -1:
                        # Extract the translated HTML (including the tags)
                        translated_html = translated_text[start_pos + len(block_start):end_pos].strip()
                        
                        # Parse the translated HTML
                        try:
                            translated_soup = BeautifulSoup(translated_html, "html.parser")
                            # Replace the original paragraph with the translated one
                            # but keep the original tag name and attributes
                            if translated_soup.body:
                                translated_element = translated_soup.body.contents[0]
                            else:
                                translated_element = translated_soup.contents[0]
                                
                            # Copy the translated content to the original element
                            p.clear()
                            p.append(BeautifulSoup(str(translated_element), "html.parser"))
                        except Exception as e:
                            logger.error(f"Error parsing translated HTML for block {idx}: {e}")
                            # If parsing fails, try a direct replacement
                            try:
                                p.string = BeautifulSoup(translated_html, "html.parser").get_text()
                            except:
                                # Last resort fallback
                                logger.error(f"Fallback string replacement failed for block {idx}")
                                pass
                    else:
                        logger.warning(f"Could not find block markers for block {idx}")
            except Exception as e:
                logger.error(f"Translation API error: {e}")
                continue

        # Regenerate the HTML with translations
        result = _unmask(str(soup), mapping)
        
        # Cache the result in Redis for 1 hour
        if set_cached_translation(cache_key, result, timeout=60*60):
            logger.info(f"Successfully cached translation to Redis")
        else:
            logger.warning(f"Failed to cache translation to Redis")
            
        logger.info(f"Successfully translated content to {target_lang_name}")
        
        return result
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return html  # Return original on error 