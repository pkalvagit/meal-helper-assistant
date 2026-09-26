"""Google Places API (New) search -> the URL file menu_url_finder.py consumes.

Two entry points, one per endpoint:

    search_nearby()  places:searchNearby -- structured filters, HARD circular
                     radius, no free text. Right for systematically sweeping an
                     area by cuisine type.

    search_text()    places:searchText -- free text ("italian rooftop patio"),
                     plus minRating / openNow / priceLevels. Its radius is only
                     a *bias*, so results are re-filtered by real distance here.

Then `write_urls_file()` emits "<place_id>, <websiteUri>" lines, which is
exactly what menu_url_finder.load_urls() reads.

    python places_search.py nearby --lat 38.9586 --lng -77.3570 --radius 5000 \
        --types italian_restaurant -o urls.txt
    python places_search.py text "italian restaurant with a rooftop patio" \
        --lat 38.9586 --lng -77.3570 --radius 5000 -o urls.txt

Key from --api-key, GOOGLE_MAPS_API_KEY, or GOOGLE_PLACES_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import requests
from pydantic import BaseModel

from menu_url_finder import build_session, configure_tls

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

# X-Goog-FieldMask is mandatory -- omit it and the API returns 400. Every field
# you add can move the call into a pricier SKU: id/displayName/location are
# cheap, while websiteUri/rating/priceLevel bill at Enterprise. Ask only for
# what you use.
FIELDS_CORE = (
    "places.id", "places.displayName", "places.location",
    "places.primaryType", "places.formattedAddress",
)
FIELDS_WITH_WEBSITE = FIELDS_CORE + (
    "places.websiteUri", "places.rating", "places.userRatingCount",
    "places.priceLevel", "places.priceRange", "places.googleMapsUri",
)

# Cuisine-level types, so "italian restaurant" needs no free-text query at all.
CUISINE_TYPES = (
    "italian_restaurant", "chinese_restaurant", "mexican_restaurant",
    "japanese_restaurant", "indian_restaurant", "thai_restaurant",
    "korean_restaurant", "vietnamese_restaurant", "french_restaurant",
    "greek_restaurant", "spanish_restaurant", "turkish_restaurant",
    "lebanese_restaurant", "middle_eastern_restaurant", "brazilian_restaurant",
    "american_restaurant", "afghani_restaurant", "indonesian_restaurant",
    "pizza_restaurant", "sushi_restaurant", "ramen_restaurant", "steak_house",
    "seafood_restaurant", "barbecue_restaurant", "vegan_restaurant",
    "vegetarian_restaurant", "fine_dining_restaurant", "breakfast_restaurant",
    "brunch_restaurant", "fast_food_restaurant", "hamburger_restaurant",
    "sandwich_shop", "dessert_restaurant", "cafe", "coffee_shop", "bakery",
    "bar", "pub", "wine_bar",
)

EARTH_RADIUS_M = 6_371_000


class RestaurantPlace(BaseModel):
    """Flat, minimal record for one restaurant returned by a Places search.

    Field names intentionally match `_normalize()`'s row keys so a plain
    dict from the existing pipeline can be loaded directly with
    `RestaurantPlace(**row)`.
    """
    place_id: str | None = None
    distance_m: float | None = None
    name: str | None = None
    website_uri: str | None = None
    google_maps_uri: str | None = None
    address: str | None = None
    rating: float | None = None
    price_level: str | None = None
    price_range: dict | None = None


def resolve_api_key(explicit: str | None = None) -> str:
    key = (
        explicit
        or os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("GOOGLE_PLACES_API_KEY")
    )
    if not key:
        raise SystemExit(
            "No API key. Pass --api-key or export GOOGLE_MAPS_API_KEY."
        )
    return key


def metres_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


# --------------------------------------------------------------------------- #
# Request bodies (pure -- kept separate so they can be asserted in tests)
# --------------------------------------------------------------------------- #

def build_nearby_body(
    latitude: float,
    longitude: float,
    radius_m: float,
    included_types: tuple[str, ...] = ("restaurant",),
    max_results: int = 20,
    rank_by: str = "DISTANCE",
    primary_only: bool = False,
    language_code: str = "en",
    region_code: str | None = None,
    excluded_types: tuple[str, ...] = (),
) -> dict:
    """searchNearby body. `locationRestriction.circle` is a hard boundary."""
    # includedTypes matches ANY of a place's types; includedPrimaryTypes matches
    # only its main category (a pub also tagged italian won't come back).
    type_key = "includedPrimaryTypes" if primary_only else "includedTypes"
    body: dict = {
        type_key: list(included_types),
        # Capped at 20 by the API, and searchNearby has no pagination -- see the
        # tiling note in the module docstring's companion README.
        "maxResultCount": min(max_results, 20),
        "rankPreference": rank_by,
        "languageCode": language_code,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_m),
            }
        },
    }
    if excluded_types:
        body["excludedTypes"] = list(excluded_types)
    if region_code:
        body["regionCode"] = region_code
    return body


def build_text_body(
    text_query: str,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_m: float | None = None,
    included_type: str | None = "restaurant",
    min_rating: float | None = None,
    open_now: bool | None = None,
    price_levels: tuple[str, ...] = (),
    rank_by: str = "RELEVANCE",
    page_size: int = 20,
    page_token: str | None = None,
    language_code: str = "en",
    region_code: str | None = None,
    strict_type: bool = False,
) -> dict:
    """searchText body.

    `locationBias` is a bias, not a boundary -- the API may return places
    outside the circle. (Its hard `locationRestriction` accepts a rectangle
    only, which is why search_text() re-filters by computed distance instead.)
    """
    body: dict = {
        "textQuery": text_query,
        "pageSize": min(page_size, 20),
        "rankPreference": rank_by,
        "languageCode": language_code,
    }
    if included_type:
        body["includedType"] = included_type          # singular, unlike nearby
        body["strictTypeFiltering"] = strict_type
    if latitude is not None and longitude is not None and radius_m:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_m),
            }
        }
    if min_rating is not None:
        body["minRating"] = min_rating
    if open_now is not None:
        body["openNow"] = open_now
    if price_levels:
        body["priceLevels"] = list(price_levels)
    if region_code:
        body["regionCode"] = region_code
    if page_token:
        body["pageToken"] = page_token
    return body


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #

def _post(
    url: str,
    body: dict,
    api_key: str,
    field_mask: tuple[str, ...],
    session: requests.Session,
    timeout: float,
) -> dict:
    """POST and normalise both transport and Google-side errors."""
    try:
        resp = session.post(
            url,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": ",".join(field_mask),
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        hint = None
        if isinstance(exc, requests.exceptions.SSLError):
            hint = "TLS verification failed - use --ca-bundle / --insecure."
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "hint": hint,
                "places": []}

    try:
        payload = resp.json()
    except ValueError:
        return {"ok": False, "error": f"HTTP {resp.status_code}: non-JSON response",
                "places": []}

    if resp.status_code >= 400:
        # Google's shape: {"error": {"code", "message", "status"}}. The message
        # names the offending field, so pass it through verbatim.
        err = payload.get("error", {})
        return {
            "ok": False,
            "error": f"HTTP {resp.status_code} {err.get('status', '')}: "
                     f"{err.get('message', payload)}",
            "places": [],
        }

    return {"ok": True, "error": None, "places": payload.get("places", []),
            "next_page_token": payload.get("nextPageToken")}


def _normalize(places: list[dict], center: tuple[float, float] | None) -> list[dict]:
    """Flatten Places payloads into flat rows, adding distance when we can."""
    rows = []
    for p in places:
        loc = p.get("location") or {}
        lat, lng = loc.get("latitude"), loc.get("longitude")
        row = {
            "place_id": p.get("id"),
            "name": (p.get("displayName") or {}).get("text"),
            "website_uri": p.get("websiteUri"),
            "google_maps_uri": p.get("googleMapsUri"),
            "address": p.get("formattedAddress"),
            "primary_type": p.get("primaryType"),
            "rating": p.get("rating"),
            "user_rating_count": p.get("userRatingCount"),
            "price_level": p.get("priceLevel"),
            "price_range": p.get("priceRange"),
            "latitude": lat,
            "longitude": lng,
            "distance_m": None,
        }
        if center and lat is not None and lng is not None:
            row["distance_m"] = round(metres_between(center[0], center[1], lat, lng), 1)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# Method 1 -- Nearby Search (structured, hard radius, no free text)
# --------------------------------------------------------------------------- #

def search_nearby(
    latitude: float,
    longitude: float,
    radius_m: float,
    included_types: tuple[str, ...] = ("restaurant",),
    api_key: str | None = None,
    max_results: int = 20,
    rank_by: str = "DISTANCE",
    primary_only: bool = False,
    excluded_types: tuple[str, ...] = (),
    want_website: bool = True,
    language_code: str = "en",
    region_code: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 15.0,
) -> dict:
    """places:searchNearby -- deterministic sweep of a circle by place type.

    There is no free-text parameter on this endpoint (the legacy API's
    `keyword` was dropped). For "italian restaurant", pass
    included_types=("italian_restaurant",) -- see CUISINE_TYPES.

    Returns {"ok", "error", "places": [flat rows], "truncated"}.
    """
    api_key = resolve_api_key(api_key)
    session = session or build_session()
    body = build_nearby_body(
        latitude, longitude, radius_m, included_types=included_types,
        max_results=max_results, rank_by=rank_by, primary_only=primary_only,
        language_code=language_code, region_code=region_code,
        excluded_types=excluded_types,
    )
    mask = FIELDS_WITH_WEBSITE if want_website else FIELDS_CORE
    res = _post(NEARBY_URL, body, api_key, mask, session, timeout)
    if not res["ok"]:
        return {**res, "truncated": False}

    rows = _normalize(res["places"], (latitude, longitude))
    return {
        "ok": True,
        "error": None,
        "places": rows,
        # 20 is the API's ceiling and there's no pagination: a full result set
        # means the circle is denser than one call can express. Shrink the
        # radius and tile, or the tail is invisible to you.
        "truncated": len(rows) >= min(max_results, 20),
        "query": {"endpoint": "searchNearby", "center": [latitude, longitude],
                  "radius_m": radius_m, "types": list(included_types)},
    }


# --------------------------------------------------------------------------- #
# Method 2 -- Text Search (free text, radius is only a bias)
# --------------------------------------------------------------------------- #

def search_text(
    text_query: str,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_m: float | None = None,
    api_key: str | None = None,
    included_type: str | None = "restaurant",
    min_rating: float | None = None,
    open_now: bool | None = None,
    price_levels: tuple[str, ...] = (),
    rank_by: str = "RELEVANCE",
    max_pages: int = 1,
    page_size: int = 20,
    enforce_radius: bool = True,
    strict_type: bool = False,
    want_website: bool = True,
    language_code: str = "en",
    region_code: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 15.0,
) -> dict:
    """places:searchText -- free-text query, optional rating/openNow filters.

    `enforce_radius` post-filters on real distance, because locationBias lets
    the API return places beyond the circle. Set it False to keep everything.
    """
    api_key = resolve_api_key(api_key)
    session = session or build_session()
    mask = FIELDS_WITH_WEBSITE if want_website else FIELDS_CORE
    center = (latitude, longitude) if latitude is not None and longitude is not None else None

    rows: list[dict] = []
    token: str | None = None
    for _ in range(max(1, max_pages)):
        body = build_text_body(
            text_query, latitude=latitude, longitude=longitude, radius_m=radius_m,
            included_type=included_type, min_rating=min_rating, open_now=open_now,
            price_levels=price_levels, rank_by=rank_by, page_size=page_size,
            page_token=token, language_code=language_code, region_code=region_code,
            strict_type=strict_type,
        )
        res = _post(TEXT_URL, body, api_key, mask, session, timeout)
        if not res["ok"]:
            # Return what we already have alongside the error rather than losing it.
            return {**res, "places": rows, "dropped_outside_radius": 0}
        rows.extend(_normalize(res["places"], center))
        token = res.get("next_page_token")
        if not token:
            break

    dropped = 0
    if enforce_radius and center and radius_m:
        keep = [r for r in rows
                if r["distance_m"] is not None and r["distance_m"] <= radius_m]
        dropped = len(rows) - len(keep)
        rows = keep

    return {
        "ok": True,
        "error": None,
        "places": rows,
        "dropped_outside_radius": dropped,
        "query": {"endpoint": "searchText", "text_query": text_query,
                  "center": list(center) if center else None, "radius_m": radius_m},
    }


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def to_restaurant_places(places: list[dict]) -> list[RestaurantPlace]:
    """Build validated RestaurantPlace models from `_normalize()`'s flat rows."""
    return [RestaurantPlace(**p) for p in places]


def write_restaurant_places_file(places: list[dict], path: str | Path) -> int:
    """Write id/distance/name/website/google_url/address/rating as a JSON array.

    Each element is a `RestaurantPlace`, dumped via Pydantic so field
    validation/typing is enforced before anything hits disk.
    """
    records = to_restaurant_places(places)
    Path(path).write_text(
        json.dumps([r.model_dump() for r in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(records)


def write_urls_file(places: list[dict], path: str | Path) -> dict:
    """Write "<place_id>, <websiteUri>" lines for menu_url_finder.load_urls()."""
    lines, no_site = [], []
    for p in places:
        if p.get("website_uri") and p.get("place_id"):
            lines.append(f"{p['place_id']}, {p['website_uri']}")
        else:
            no_site.append(p.get("name") or p.get("place_id"))

    Path(path).write_text(
        "# generated by places_search.py\n"
        "# <place_id>, <websiteUri>\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return {"written": len(lines), "skipped_no_website": no_site}


def _report(result: dict, urls_path: str | None, json_path: str | None,
            restaurants_json_path: str | None = None) -> None:
    if not result["ok"]:
        print(f"Search failed: {result['error']}", file=sys.stderr)
        if result.get("hint"):
            print(f"  -> {result['hint']}", file=sys.stderr)

    places = result["places"]
    print(f"\n{len(places)} place(s)", file=sys.stderr)
    for p in places:
        dist = f"{p['distance_m']:>7.0f}m" if p["distance_m"] is not None else "      -"
        site = p["website_uri"] or "(no website)"
        print(f"  {dist}  {(p['name'] or '?')[:34]:<34} {site}", file=sys.stderr)

    if result.get("dropped_outside_radius"):
        print(f"\n{result['dropped_outside_radius']} result(s) fell outside the radius "
              f"and were dropped (locationBias is a bias, not a boundary).",
              file=sys.stderr)
    if result.get("truncated"):
        print("\nHit the 20-result cap and searchNearby has no pagination - there are "
              "almost certainly more places here.\n"
              "  Shrink --radius and run several overlapping searches to cover the area.",
              file=sys.stderr)

    if json_path:
        Path(json_path).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"\nWrote {json_path}", file=sys.stderr)

    if restaurants_json_path:
        n = write_restaurant_places_file(places, restaurants_json_path)
        print(f"Wrote {restaurants_json_path}: {n} restaurant record(s) "
              f"(id, distance, name, website, google_maps_uri, address, rating)",
              file=sys.stderr)

    # if urls_path:
    #     stats = write_urls_file(places, urls_path)
    #     print(f"Wrote {urls_path}: {stats['written']} site(s)", file=sys.stderr)
    #     if stats["skipped_no_website"]:
    #         print(f"  {len(stats['skipped_no_website'])} place(s) have no websiteUri "
    #               f"and were skipped (no site = no menu to fetch)", file=sys.stderr)
    #     print(f"\nNext:  python menu_url_finder.py {urls_path} -o menu_urls.json",
    #           file=sys.stderr)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--api-key", help="else GOOGLE_MAPS_API_KEY / GOOGLE_PLACES_API_KEY")
    parent.add_argument("-o", "--out", default="urls.txt", help="URL file for menu_url_finder")
    parent.add_argument("--json", dest="json_path", help="also dump full results here")
    parent.add_argument("--restaurants-json", dest="restaurants_json_path",
                        help="write id/distance/name/website/google_maps_uri/"
                             "address/rating as a JSON array (Pydantic-validated)")
    parent.add_argument("--no-website", action="store_true",
                        help="cheaper field mask; omits websiteUri (and no URL file)")
    parent.add_argument("--language", default="en")
    parent.add_argument("--region")
    parent.add_argument("--ca-bundle", metavar="PEM", help="for TLS-inspecting proxies")
    parent.add_argument("--insecure", action="store_true", help="skip TLS verification")

    p = argparse.ArgumentParser(description="Google Places search -> menu_url_finder input.")
    sub = p.add_subparsers(dest="mode", required=True)

    n = sub.add_parser("nearby", parents=[parent],
                       help="searchNearby: hard radius, type filters, no free text")
    n.add_argument("--lat", type=float, required=True)
    n.add_argument("--lng", type=float, required=True)
    n.add_argument("--radius", type=float, default=2000.0, help="metres")
    n.add_argument("--types", nargs="+", default=["restaurant"],
                   help="e.g. italian_restaurant (see CUISINE_TYPES)")
    n.add_argument("--exclude-types", nargs="+", default=[])
    n.add_argument("--primary-only", action="store_true",
                   help="match main category only (includedPrimaryTypes)")
    n.add_argument("--max-results", type=int, default=20)
    n.add_argument("--rank", default="DISTANCE", choices=["DISTANCE", "POPULARITY"])

    t = sub.add_parser("text", parents=[parent],
                       help="searchText: free text, rating/openNow filters")
    t.add_argument("query", help='e.g. "italian restaurant with a rooftop patio"')
    t.add_argument("--lat", type=float)
    t.add_argument("--lng", type=float)
    t.add_argument("--radius", type=float, help="metres (bias; enforced client-side)")
    t.add_argument("--type", default="restaurant", help="includedType, or '' for none")
    t.add_argument("--min-rating", type=float)
    t.add_argument("--open-now", action="store_true")
    t.add_argument("--price-levels", nargs="+", default=[],
                   help="e.g. PRICE_LEVEL_MODERATE PRICE_LEVEL_EXPENSIVE")
    t.add_argument("--pages", type=int, default=1, help="pages to follow (20 each)")
    t.add_argument("--keep-outside-radius", action="store_true")
    t.add_argument("--strict-type", action="store_true")
    t.add_argument("--rank", default="RELEVANCE", choices=["RELEVANCE", "DISTANCE"])

    args = p.parse_args(argv)
    configure_tls(ca_bundle=args.ca_bundle, insecure=args.insecure)
    if args.insecure:
        print("WARNING: TLS verification disabled (--insecure).", file=sys.stderr)

    common = dict(api_key=args.api_key, want_website=not args.no_website,
                  language_code=args.language, region_code=args.region)

    if args.mode == "nearby":
        result = search_nearby(
            args.lat, args.lng, args.radius,
            included_types=tuple(args.types), excluded_types=tuple(args.exclude_types),
            max_results=args.max_results, rank_by=args.rank,
            primary_only=args.primary_only, **common,
        )
    else:
        result = search_text(
            args.query, latitude=args.lat, longitude=args.lng, radius_m=args.radius,
            included_type=args.type or None, min_rating=args.min_rating,
            open_now=True if args.open_now else None,
            price_levels=tuple(args.price_levels), rank_by=args.rank,
            max_pages=args.pages, enforce_radius=not args.keep_outside_radius,
            strict_type=args.strict_type, **common,
        )

    _report(result, None if args.no_website else args.out, args.json_path,
            args.restaurants_json_path)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
