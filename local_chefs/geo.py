import logging
from decimal import Decimal
from math import isnan
from typing import Optional, Tuple

import pgeocode
from django_countries import countries
from django.utils import timezone

from .models import PostalCode

logger = logging.getLogger(__name__)

_nom_cache = {}


def _normalize_country(country) -> str:
    if not country:
        return 'US'
    try:
        code = getattr(country, 'code', None)
        if code:
            return code.upper()
    except Exception:
        pass
    country_str = str(country).strip()
    if len(country_str) == 2:
        return country_str.upper()
    try:
        # django-countries raises KeyError if name not found
        mapped = countries.by_name(country_str)
        if mapped:
            return mapped.upper()
    except KeyError:
        pass
    return country_str[:2].upper()


def _get_nominatim(country_code: str) -> Optional[pgeocode.Nominatim]:
    if not country_code:
        return None
    country_code = country_code.upper()
    if country_code not in _nom_cache:
        try:
            _nom_cache[country_code] = pgeocode.Nominatim(country_code)
        except Exception as exc:
            logger.warning("Unable to load postal geocoder for %s: %s", country_code, exc)
            _nom_cache[country_code] = None
    return _nom_cache.get(country_code)


def ensure_postal_code_coordinates(code: str, country) -> Optional[PostalCode]:
    """Ensure the PostalCode row has latitude/longitude saved. Returns the row or None."""
    if not code:
        return None
    normalized = PostalCode.normalize_code(code)
    if not normalized:
        return None
    country_code = _normalize_country(country)
    postal_code, _ = PostalCode.objects.get_or_create(
        code=normalized,
        country=country_code,
        defaults={'display_code': code},
    )
    if postal_code.latitude is not None and postal_code.longitude is not None:
        return postal_code

    nominatim = _get_nominatim(country_code)
    if not nominatim:
        return postal_code

    try:
        record = nominatim.query_postal_code(code)
    except Exception as exc:
        logger.warning("Postal geocode lookup failed for %s %s: %s", country_code, code, exc)
        return postal_code

    if record is None:
        return postal_code

    lat = getattr(record, 'latitude', None)
    lon = getattr(record, 'longitude', None)

    def _valid(value):
        if value is None:
            return False
        try:
            return not isnan(float(value))
        except Exception:
            return False

    if not (_valid(lat) and _valid(lon)):
        return postal_code

    postal_code.latitude = Decimal(str(float(lat)))
    postal_code.longitude = Decimal(str(float(lon)))
    postal_code.geocoded_at = timezone.now()
    postal_code.save(update_fields=['latitude', 'longitude', 'geocoded_at'])
    return postal_code
