"""Společné nastavení testů.

Testy běží bez reálných API klíčů – main.py ale čte TELEGRAM_BOT_TOKEN
už při importu, proto ho nastavíme dřív, než se cokoliv importuje.
"""
import os
import sys

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN_NOT_REAL")

# Izolace od lokálního .env (main.py volá load_dotenv(), který existující
# proměnné nepřepisuje): tyto proměnné mají v main.py fail-closed validaci
# při importu a vývojářova konfigurace by jinak mohla shodit celou test suite.
for _var in ("TELEGRAM_ALLOWED_USERS", "MAP_TOKEN", "MAP_VIEW_TOKEN",
             "BOT_LANGUAGE", "CATEGORIES"):
    os.environ[_var] = ""
# Limit délky videa čte extractor.py při importu – nevalidní hodnota
# ve vývojářově .env by shodila import; testy počítají s výchozí 10.
os.environ["MAX_VIDEO_MINUTES"] = "10"

# Import modulů projektu z kořene repa (testy běží z podsložky tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_place(**overrides) -> dict:
    """Továrna na místo ve tvaru, který vrací sheets.read_rows()."""
    place = {
        "row": 2,
        "date": "2026-07-01 12:00",
        "url": "https://www.facebook.com/reel/123",
        "author": "autor",
        "title": "titulek",
        "location_name": "Koupaliště Slaný",
        "lat": 50.23,
        "lng": 14.09,
        "category": "koupání",
        "tags": "outdoor,s dětmi",
        "summary": "Moderní koupaliště s bazény.",
        "source": "facebook",
        "group_id": "",
        "video_id": "123",
        "visited": False,
        "place_id": "",
        "maps_url": "",
        "geo_source": "gemini",
    }
    place.update(overrides)
    return place
