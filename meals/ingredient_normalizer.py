import json
import logging
from typing import Dict, List

from shared.utils import get_groq_client

# Local fallback synonyms if the API fails
LOCAL_SYNONYMS: Dict[str, str] = {
    "bell peppers": "bell pepper",
    "garbanzo beans": "chickpeas",
}

# Simple in-memory cache for normalization results
_normalization_cache: Dict[str, str] = {}


def normalize_ingredient(name: str) -> str:
    """Return a canonical ingredient name.

    Attempts to use the OpenAI Responses API to canonicalize the ingredient
    name. Results are cached locally. If the API call fails, falls back to the
    ``LOCAL_SYNONYMS`` dictionary or the lower-cased input.
    """
    if not name:
        return ""

    key = name.strip().lower()
    if key in _normalization_cache:
        return _normalization_cache[key]

    prompt = (
        "Return the canonical, singular form of this ingredient name: \n"
        f"{name}\n"
        "Respond with only the canonical name."
    )

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        canonical = response.choices[0].message.content.strip().lower()
        if canonical:
            _normalization_cache[key] = canonical
            return canonical
    except Exception as exc:  # pragma: no cover - log but continue
        logging.warning("normalize_ingredient API failure for %s: %s", name, exc)

    canonical = LOCAL_SYNONYMS.get(key, key)
    _normalization_cache[key] = canonical
    return canonical


def aggregate_items(items: List[Dict[str, float]]) -> Dict[str, float]:
    """Aggregate quantities of items using normalized ingredient names."""
    aggregated: Dict[str, float] = {}
    for item in items:
        ingredient = item.get("ingredient", "")
        quantity = item.get("quantity", 0) or 0
        normalized = normalize_ingredient(ingredient)
        aggregated[normalized] = aggregated.get(normalized, 0) + quantity
    return aggregated
