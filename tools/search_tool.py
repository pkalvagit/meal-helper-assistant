"""
Restaurant search tool - wraps places_search.py
"""
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

from langchain.tools import tool

# Add utils to path
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from places_search import search_nearby, search_text


def get_api_key() -> str:
    """Get Google Maps API key from environment."""
    return os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY") or ""


@tool
def search_restaurants_nearby(
    lat: float,
    lng: float,
    radius: int = 5000,
    types: str = "restaurant",
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Search for restaurants near a specific location.

    Args:
        lat: Latitude (e.g., 38.9586)
        lng: Longitude (e.g., -77.3570)
        radius: Search radius in meters, default 5000 (max 50000)
        types: Restaurant type as string, default "restaurant". Examples: "italian_restaurant", "pizza_restaurant"
        max_results: Maximum number of results, default 20

    Returns:
        List of restaurants with name, address, rating, website, types
    """
    try:
        # Get API key from environment
        api_key = get_api_key()
        if not api_key:
            return [{"error": "GOOGLE_MAPS_API_KEY not set. Please add it to .env file."}]

        # Handle types parameter - convert to list
        if isinstance(types, list):
            type_list = types if types else ["restaurant"]
        elif isinstance(types, str):
            type_list = [t.strip() for t in types.split(",")] if types else ["restaurant"]
        else:
            type_list = ["restaurant"]

        results = search_nearby(
            latitude=lat,
            longitude=lng,
            radius_m=radius,
            included_types=tuple(type_list),
            max_results=max_results,
            api_key=api_key
        )

        # Check for errors
        if not results.get("ok"):
            return [{"error": results.get("error", "Unknown error")}]

        # Extract places from result
        places = results.get("places", [])
        if not places:
            return [{"error": "No restaurants found in this area"}]

        # Format for agent
        formatted = []
        for r in places:
            formatted.append({
                "id": r.get("place_id"),
                "name": r.get("name"),
                "address": r.get("address"),
                "rating": r.get("rating"),
                "website": r.get("website_uri"),
                "types": [r.get("primary_type")] if r.get("primary_type") else [],
                "distance_m": r.get("distance_m"),
            })

        return formatted

    except Exception as e:
        return [{"error": str(e)}]


@tool
def search_restaurants_by_query(
    query: str,
    lat: float,
    lng: float,
    radius: int = 5000,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Search restaurants using natural language query.

    Args:
        query: Natural language search (e.g., "italian restaurants with outdoor seating")
        lat: Center latitude
        lng: Center longitude
        radius: Search radius in meters
        max_results: Maximum results

    Returns:
        List of matching restaurants
    """
    try:
        # Get API key from environment
        api_key = get_api_key()
        if not api_key:
            return [{"error": "GOOGLE_MAPS_API_KEY not set. Please add it to .env file."}]

        # Calculate max_pages from max_results (20 results per page)
        max_pages = max(1, (max_results + 19) // 20)

        results = search_text(
            text_query=query,
            latitude=lat,
            longitude=lng,
            radius_m=radius,
            max_pages=max_pages,
            api_key=api_key
        )

        # Check for errors
        if not results.get("ok"):
            return [{"error": results.get("error", "Unknown error")}]

        # Extract places from result
        places = results.get("places", [])
        if not places:
            return [{"error": "No restaurants found matching your query"}]

        # Format for agent
        formatted = []
        for r in places:
            formatted.append({
                "id": r.get("place_id"),
                "name": r.get("name"),
                "address": r.get("address"),
                "rating": r.get("rating"),
                "website": r.get("website_uri"),
                "types": [r.get("primary_type")] if r.get("primary_type") else [],
                "distance_m": r.get("distance_m") if "distance_m" in r else None,
            })

        return formatted

    except Exception as e:
        return [{"error": str(e)}]
