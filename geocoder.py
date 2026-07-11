"""Geokódování přes Google Places API (New) + stavba odkazu na Google Maps.

Best-effort: když klíč chybí nebo Places nic nenajde, vrací None a pipeline
pokračuje s odhadem souřadnic od Gemini (geo_source = "gemini").
"""
import math
import os
from urllib.parse import quote_plus

import httpx


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine – vzdálenost dvou souřadnic v km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
_FIELDS = "places.id,places.displayName,places.formattedAddress,places.location"


def maps_link(place_id: str = "", name: str = "",
              lat: float | None = None, lng: float | None = None) -> str:
    """Odkaz na Google Maps – oficiální Maps URLs formát (funguje i v mobilní aplikaci).

    Formát `?q=place_id:...` mobilní aplikace neumí (hledá ho jako text),
    proto `api=1` + `query_place_id`. Parametr `query` je u query_place_id
    povinný – přikládáme souřadnice, případně název.
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
        lat, lng = float(loc["latitude"]), float(loc["longitude"])
        return {
            "place_id": pid,
            "lat": lat,
            "lng": lng,
            "address": p.get("formattedAddress", ""),
            "maps_url": maps_link(pid, lat=lat, lng=lng),
        }
    except Exception as e:
        # Geokódování nesmí shodit zpracování videa – jen zalogovat
        print(f"[geocoder] chyba: {type(e).__name__}: {e}")
        return None
