# shared/google_places.py

import time
import requests
from django.conf import settings
import os
import dotenv
import json
import logging

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
API_KEY = os.getenv("PLACES_API_KEY")

def nearby_supermarkets(lat: float, lng: float, radius: int = 5000, max_results: int = 10) -> list[dict]:
    """Search for supermarkets near the given latitude and longitude using the new Places API."""
    
    if not API_KEY:
        logger.error("PLACES_API_KEY is not set in the environment variables.")
        return []

    payload = {
        "includedTypes": ["supermarket"],
        "maxResultCount": max_results,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(lat),
                    "longitude": float(lng)
                },
                "radius": float(radius)
            }
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': API_KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.location'
    }

    logger.info(f"Sending request to Google Places API: URL={GOOGLE_NEARBY_URL}, Headers={headers}, Payload={json.dumps(payload)}")

    try:
        resp = requests.post(GOOGLE_NEARBY_URL, headers=headers, json=payload)
        logger.info(f"Received response: Status={resp.status_code}, Body={resp.text[:500]}...")
        resp.raise_for_status()
        data = resp.json()
        
        places = data.get("places", []) 
        logger.info(f"Found {len(places)} supermarkets.")
        return places

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Google Places API request: {e}")
        logger.error(f"Request details: URL={GOOGLE_NEARBY_URL}, Headers={headers}, Payload={json.dumps(payload)}")
        return []
    except json.JSONDecodeError as e:
         logger.error(f"Error decoding JSON response from Google Places API: {e}")
         logger.error(f"Response text: {resp.text}")
         return []
    except Exception as e:
        logger.error(f"An unexpected error occurred in nearby_supermarkets: {e}")
        return []