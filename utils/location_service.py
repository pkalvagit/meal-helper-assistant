"""
Location service - fetch latitude/longitude from IP or address.

Two main functions:
1. get_current_location() - Auto-detect location from IP address
2. geocode_address() - Convert address string to lat/lng using Google Maps
"""
import os
import requests
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger("location-service")


def get_current_location_from_ip() -> Optional[Dict[str, Any]]:
    """
    Auto-detect user's location from their IP address.

    Uses ipapi.co free service (no API key needed, 1000 requests/day).

    Returns:
        {
            "latitude": 38.9586,
            "longitude": -77.3570,
            "city": "Reston",
            "region": "Virginia",
            "country": "US",
            "source": "ip"
        }
        or None if detection fails
    """
    try:
        # Try ipapi.co first (free, no key needed)
        response = requests.get(
            "https://ipapi.co/json/",
            timeout=5,
            verify=not os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"
        )

        if response.status_code == 200:
            data = response.json()

            # Check if we got valid data
            if data.get("latitude") and data.get("longitude"):
                location = {
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": data.get("country_name"),
                    "postal_code": data.get("postal"),
                    "source": "ip"
                }
                logger.info(f"Detected location from IP: {location['city']}, {location['region']} ({location['latitude']}, {location['longitude']})")
                return location

        # Fallback: Try ip-api.com (also free, different rate limits)
        response = requests.get(
            "http://ip-api.com/json/",
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "success":
                location = {
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": data.get("country"),
                    "postal_code": data.get("zip"),
                    "source": "ip"
                }
                logger.info(f"Detected location from IP (fallback): {location['city']}, {location['region']}")
                return location

    except Exception as e:
        logger.warning(f"Failed to detect location from IP: {e}")

    return None


def geocode_address(address: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Convert address string to latitude/longitude using Google Maps APIs.

    Tries Geocoding API first, then falls back to Places Text Search API.

    Args:
        address: Address string like "New York, NY" or "123 Main St, Boston"
        api_key: Google Maps API key (defaults to GOOGLE_MAPS_API_KEY env var)

    Returns:
        {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "formatted_address": "New York, NY, USA",
            "city": "New York",
            "state": "New York",
            "country": "United States",
            "source": "geocode"
        }
        or None if geocoding fails
    """
    api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY")

    if not api_key:
        logger.error("No Google Maps API key found for geocoding")
        return None

    # Try Method 1: Geocoding API (more accurate, but might be disabled)
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": address,
                "key": api_key
            },
            timeout=10,
            verify=not os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                location = result["geometry"]["location"]

                # Extract address components
                components = {}
                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "locality" in types:
                        components["city"] = component["long_name"]
                    elif "administrative_area_level_1" in types:
                        components["state"] = component["long_name"]
                    elif "country" in types:
                        components["country"] = component["long_name"]
                    elif "postal_code" in types:
                        components["postal_code"] = component["long_name"]

                geocoded = {
                    "latitude": location["lat"],
                    "longitude": location["lng"],
                    "formatted_address": result["formatted_address"],
                    "city": components.get("city"),
                    "state": components.get("state"),
                    "country": components.get("country"),
                    "postal_code": components.get("postal_code"),
                    "source": "geocode"
                }

                logger.info(f"Geocoded '{address}' -> {geocoded['formatted_address']} ({geocoded['latitude']}, {geocoded['longitude']})")
                return geocoded
            elif data.get("status") == "REQUEST_DENIED":
                # Geocoding API not enabled - fall back to Places API
                logger.debug(f"Geocoding API not enabled, trying Places API fallback")
            else:
                error = data.get("status", "Unknown error")
                logger.warning(f"Geocoding failed for '{address}': {error}")

    except Exception as e:
        logger.debug(f"Geocoding API failed: {e}, trying fallback")

    # Method 2: Fallback to Places Text Search API (already enabled for restaurant search)
    try:
        # Improve query for ZIP codes - add "USA" to disambiguate
        search_query = address
        if address.strip().isdigit() and len(address.strip()) == 5:
            search_query = f"{address}, USA"
            logger.debug(f"ZIP code detected, searching for: {search_query}")

        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location",
                "Content-Type": "application/json",
            },
            json={
                "textQuery": search_query,
                "languageCode": "en",
            },
            timeout=10,
            verify=not os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"
        )

        if response.status_code == 200:
            data = response.json()
            places = data.get("places", [])

            if places:
                place = places[0]  # Take first result
                location = place.get("location", {})

                geocoded = {
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "formatted_address": place.get("formattedAddress", address),
                    "city": None,
                    "state": None,
                    "country": None,
                    "postal_code": None,
                    "source": "places_api"
                }

                logger.info(f"Geocoded via Places API '{address}' -> {geocoded['formatted_address']} ({geocoded['latitude']}, {geocoded['longitude']})")
                return geocoded

    except Exception as e:
        logger.error(f"Places API fallback also failed: {e}")

    return None


def get_location(address: Optional[str] = None) -> Optional[Tuple[float, float, str]]:
    """
    Unified location getter - returns (lat, lng, description).

    Args:
        address: Optional address string. If None, auto-detects from IP.

    Returns:
        (latitude, longitude, description_string) or None

    Examples:
        >>> get_location()
        (38.9586, -77.3570, "Reston, Virginia (auto-detected)")

        >>> get_location("New York, NY")
        (40.7128, -74.0060, "New York, NY, USA")
    """
    if address:
        # User provided address - geocode it
        result = geocode_address(address)
        if result:
            return (
                result["latitude"],
                result["longitude"],
                result["formatted_address"]
            )
    else:
        # No address - auto-detect from IP
        result = get_current_location_from_ip()
        if result:
            city = result.get("city", "Unknown")
            region = result.get("region", "")
            desc = f"{city}, {region} (auto-detected)" if region else f"{city} (auto-detected)"
            return (
                result["latitude"],
                result["longitude"],
                desc
            )

    return None


# CLI for testing
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Location Service Test")
    print("=" * 60)

    # Test 1: Auto-detect from IP
    print("\n1. Auto-detecting location from IP...")
    location = get_current_location_from_ip()
    if location:
        print(f"   ✓ Detected: {location['city']}, {location['region']}")
        print(f"   ✓ Coordinates: {location['latitude']}, {location['longitude']}")
    else:
        print("   ✗ Failed to detect location")

    # Test 2: Geocode addresses
    test_addresses = [
        "New York, NY",
        "San Francisco, CA",
        "Times Square, New York",
        "1600 Pennsylvania Avenue, Washington DC"
    ]

    print("\n2. Testing address geocoding...")
    for addr in test_addresses:
        print(f"\n   Input: '{addr}'")
        result = geocode_address(addr)
        if result:
            print(f"   ✓ {result['formatted_address']}")
            print(f"   ✓ ({result['latitude']}, {result['longitude']})")
        else:
            print(f"   ✗ Failed to geocode")

    # Test 3: Unified interface
    print("\n3. Testing unified get_location()...")

    print("\n   a) No address (auto-detect):")
    result = get_location()
    if result:
        lat, lng, desc = result
        print(f"   ✓ {desc}")
        print(f"   ✓ ({lat}, {lng})")

    if len(sys.argv) > 1:
        print(f"\n   b) With address '{sys.argv[1]}':")
        result = get_location(sys.argv[1])
        if result:
            lat, lng, desc = result
            print(f"   ✓ {desc}")
            print(f"   ✓ ({lat}, {lng})")

    print("\n" + "=" * 60)
