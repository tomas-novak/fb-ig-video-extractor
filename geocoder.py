"""Geokódování přes Google Places API (New) + stavba odkazu na Google Maps.

Best-effort: když klíč chybí nebo Places nic nenajde, vrací None a pipeline
pokračuje s odhadem souřadnic od Gemini (geo_source = "gemini").
"""
import os
from urllib.parse import quote_plus

import httpx

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
_FIELDS = "places.id,places.displayName,places.formattedAddress,places.location"


def maps_link(place_id: str = "", name: str = "") -> str:
    """Odkaz na Google Maps – kanonický přes place_id, jinak hledání podle názvu."""
    if place_id:
        return f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    if name:
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name)}"
    return ""


def geocode(name: str, city: str = "") -> dict | None:
    """Najde místo přes Places Text Search. Vrací {place_id, lat, lng, address, maps_url} nebo None."""
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
            # regionCode je jen preference (většina míst je v ČR), ne tvrdý filtr
            json={"textQuery": query, "languageCode": "cs", "regionCode": "CZ"},
            timeout=15,
        )
        r.raise_for_status()
        places = r.json().get("places") or []
        if not places:
            print(f"[geocoder] nenalezeno: {query}")
            return None
        p = places[0]
        loc = p.get("location") or {}
        pid = p.get("id") or ""
        if not pid or "latitude" not in loc:
            return None
        return {
            "place_id": pid,
            "lat": float(loc["latitude"]),
            "lng": float(loc["longitude"]),
            "address": p.get("formattedAddress", ""),
            "maps_url": maps_link(pid),
        }
    except Exception as e:
        # Geokódování nesmí shodit zpracování videa – jen zalogovat
        print(f"[geocoder] chyba: {type(e).__name__}: {e}")
        return None
