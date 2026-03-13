import requests
import logging

logger = logging.getLogger(__name__)

def geocode_address(address_line, city, state, pincode):
    queries = [
        f"{address_line}, {city}, {state}, {pincode}, India",
        f"{city}, {state}, {pincode}, India",
        f"{city}, {state}, India",
    ]
    for query in queries:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "EzStay/1.0"},
                timeout=5
            )
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            logger.warning(f"Geocoding failed for query '{query}': {e}")
    return None, None