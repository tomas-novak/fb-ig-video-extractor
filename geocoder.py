"""Geocoding via Google Places API (New) + building the Google Maps link.

Best-effort: when the key is missing or Places finds nothing, returns None and
the pipeline continues with Gemini's coordinate estimate (geo_source = "gemini").
"""
import math
import os
from urllib.parse import quote_plus

import httpx


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine – distance between two coordinates in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
_FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.photos"


def maps_link(place_id: str = "", name: str = "",
              lat: float | None = None, lng: float | None = None) -> str:
    """Google Maps link – the official Maps URLs format (works in the mobile app too).

    The mobile app does not understand the `?q=place_id:...` format (it searches
    for it as plain text), hence `api=1` + `query_place_id`. The `query`
    parameter is mandatory alongside query_place_id – we pass the coordinates,
    or the name as a fallback.
    """
    if place_id:
        query = f"{lat},{lng}" if lat is not None and lng is not None else name
        if query:
            return (f"https://www.google.com/maps/search/?api=1"
                    f"&query={quote_plus(query)}&query_place_id={place_id}")
    if name:
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name)}"
    return ""


def geocode(name: str, city: str = "") -> dict | None:
    """Find a place via Places Text Search. Returns {place_id, lat, lng, address, maps_url} or None."""
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key or not name:
        return None

    query = name
    if city and city.lower() not in name.lower():
        query = f"{name}, {city}"

    try:
        r = httpx.post(
            _ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": _FIELDS,
            },
            # regionCode is only a preference (most places are in Czechia), not a hard filter
            json={"textQuery": query, "languageCode": "cs", "regionCode": "CZ"},
            timeout=15,
        )
        r.raise_for_status()
        places = r.json().get("places") or []
        if not places:
            print(f"[geocoder] not found: {query}")
            return None
        p = places[0]
        loc = p.get("location") or {}
        pid = p.get("id") or ""
        if not pid or "latitude" not in loc:
            return None
        lat, lng = float(loc["latitude"]), float(loc["longitude"])
        photos = p.get("photos") or []
        return {
            "place_id": pid,
            "lat": lat,
            "lng": lng,
            "address": p.get("formattedAddress", ""),
            "maps_url": maps_link(pid, lat=lat, lng=lng),
            # Resource name for fetch_place_photo() - not the image itself.
            "photo_name": photos[0].get("name", "") if photos else "",
        }
    except Exception as e:
        # Geocoding must not break video processing – just log it
        print(f"[geocoder] error: {type(e).__name__}: {e}")
        return None


def fetch_photo_name(place_id: str) -> str:
    """Look up a place's current photo reference from its place_id alone (no
    text search needed) - for backfilling a thumbnail onto a row that already
    has a place_id from an earlier geocode() call. Empty string if none."""
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key or not place_id:
        return ""
    try:
        r = httpx.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "photos"},
            timeout=15,
        )
        r.raise_for_status()
        photos = r.json().get("photos") or []
        return photos[0].get("name", "") if photos else ""
    except Exception as e:
        print(f"[geocoder] fetch_photo_name error: {type(e).__name__}: {e}")
        return ""


def fetch_place_photo(photo_name: str, max_width: int = 640) -> bytes | None:
    """Download a Places Photo (New) by the resource name geocode() returned.
    Counts against the separate Places Photo SKU quota (1000 free/month) -
    callers must cache the result, never call this per map view."""
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key or not photo_name:
        return None
    try:
        r = httpx.get(
            f"https://places.googleapis.com/v1/{photo_name}/media",
            params={"maxWidthPx": max_width, "key": key},
            timeout=20, follow_redirects=True,
        )
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"[geocoder] fetch_place_photo error: {type(e).__name__}: {e}")
        return None
